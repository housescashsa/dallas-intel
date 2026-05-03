"""
Dallas County Tax Roll (TRW) scraper.
Field positions from official TRW-02 file layout PDF.
"""
import re
import zipfile
import requests
from datetime import datetime, timezone
from urllib.parse import urljoin

from dallas_intel.config import TAX_ROLL_TRW_PAGE, RAW_DIR, USER_AGENT
from dallas_intel.db.init import get_connection

HEADERS = {"User-Agent": USER_AGENT}

# Slices [start_col-1 : end_col] per TRW-02 layout
SL = {
    "account":      slice(0, 34),
    "year":         slice(34, 38),
    "tax_unit":     slice(42, 76),
    "levy":         slice(76, 87),
    "homestead":    slice(87, 88),
    "date_paid":    slice(92, 100),
    "levy_balance": slice(110, 121),
    "suit":         slice(121, 122),
    "bankcode":     slice(162, 163),
    "owner":        slice(225, 265),
    "city":         slice(385, 425),
    "state":        slice(425, 427),
    "zip":          slice(427, 439),
    "parcel_no":    slice(440, 448),
    "tot_amt_due":  slice(489, 500),
}


def find_trw_url():
    r = requests.get(TAX_ROLL_TRW_PAGE, headers=HEADERS, timeout=60)
    r.raise_for_status()
    matches = re.findall(r'href="([^"]*trwfile\.\d+\.zip)"', r.text)
    candidates = [m for m in matches if "sample" not in m.lower()]
    if not candidates:
        raise RuntimeError(f"No live TRW zip found. Saw: {matches}")
    return urljoin(TAX_ROLL_TRW_PAGE, candidates[0])


def download_and_extract(url):
    fname = url.rsplit("/", 1)[-1]
    zip_path = RAW_DIR / fname
    if not zip_path.exists():
        print(f"[trw] downloading {url}")
        r = requests.get(url, headers=HEADERS, timeout=600)
        r.raise_for_status()
        zip_path.write_bytes(r.content)
    else:
        print(f"[trw] using cached {zip_path.name}")

    with zipfile.ZipFile(zip_path) as z:
        members = [n for n in z.namelist() if not n.endswith("/")]
        if not members:
            raise RuntimeError(f"Empty zip: {zip_path}")
        # Pick the LARGEST file — the data file is hundreds of MB; readme is tiny
        sized = sorted(((z.getinfo(m).file_size, m) for m in members), reverse=True)
        print(f"[trw] zip contents (size, name):")
        for sz, name in sized:
            print(f"        {sz:>13,}  {name}")
        target = sized[0][1]
        print(f"[trw] extracting largest: {target}")
        z.extract(target, RAW_DIR)
        return RAW_DIR / target


def parse_amt(s, divisor=100):
    """TRW NUMERIC dollar fields are stored as cents (no decimal point)."""
    s = s.strip().lstrip("0")
    if not s:
        return 0.0
    try:
        return int(s) / divisor
    except ValueError:
        return 0.0


def parse_record(line):
    if len(line) < 500:
        return None
    try:
        account = line[SL["account"]].strip()
        year_str = line[SL["year"]].strip()
        if not account or not year_str.isdigit():
            return None
        return {
            "tax_office_acct": account,
            "year":          int(year_str),
            "tax_unit":      line[SL["tax_unit"]].strip(),
            "levy":          parse_amt(line[SL["levy"]]),
            "levy_balance":  parse_amt(line[SL["levy_balance"]]),
            "tot_amt_due":   parse_amt(line[SL["tot_amt_due"]]),
            "date_paid":     line[SL["date_paid"]].strip(),
            "suit_flag":     line[SL["suit"]].strip(),
            "bank_flag":     line[SL["bankcode"]].strip(),
            "owner":         line[SL["owner"]].strip(),
            "parcel_no":     line[SL["parcel_no"]].strip(),
        }
    except Exception:
        return None


def run():
    url = find_trw_url()
    path = download_and_extract(url)
    size_mb = path.stat().st_size >> 20
    print(f"[trw] parsing {path.name} ({size_mb:,} MB)")

    by_account = {}
    total_lines = 0
    parsed_lines = 0
    with path.open("r", encoding="latin-1") as f:
        for line in f:
            total_lines += 1
            rec = parse_record(line)
            if not rec:
                continue
            parsed_lines += 1
            # Only delinquent: balance owed AND not yet paid
            if rec["levy_balance"] <= 0 or rec["date_paid"]:
                continue
            by_account.setdefault(rec["tax_office_acct"], []).append(rec)
            if total_lines % 500_000 == 0:
                print(f"[trw]   read {total_lines:,} lines...")

    print(f"[trw] read {total_lines:,} lines; parsed {parsed_lines:,}; {len(by_account):,} unpaid accounts")

    if not by_account:
        return

    conn = get_connection()
    conn.execute("DELETE FROM tax_delinquencies")
    current_year = datetime.now().year
    inserted = 0
    now_iso = datetime.now(timezone.utc).isoformat()

    for acct, recs in by_account.items():
        years = {r["year"] for r in recs if r["year"] < current_year}
        years_delinquent = len(years)
        total_due = sum(r["tot_amt_due"] for r in recs) or sum(r["levy_balance"] for r in recs)
        # TAX-UNIT-ACCT is the appraisal district number (DCAD account)
        # It's stored with leading zeros to 17 chars; use as-is or normalize
        tax_unit = recs[0].get("tax_unit", "").strip()
        if not tax_unit or not tax_unit.replace("0","").strip():
            continue  # skip records with no DCAD reference (BPP-only, etc.)
        # DCAD format is 17 digits left-padded with zeros
        if tax_unit.isdigit():
            dcad_acct = tax_unit.zfill(17)
        else:
            dcad_acct = tax_unit
        conn.execute("""
            INSERT INTO tax_delinquencies
                (dcad_account, tax_year, amount_due, years_delinquent, last_seen)
            VALUES (?, ?, ?, ?, ?)
        """, (dcad_acct, max(years) if years else current_year, total_due, years_delinquent, now_iso))
        inserted += 1

    conn.commit()
    summary = conn.execute("""
        SELECT
            SUM(CASE WHEN years_delinquent >= 3 THEN 1 ELSE 0 END),
            SUM(CASE WHEN years_delinquent = 2 THEN 1 ELSE 0 END),
            SUM(CASE WHEN years_delinquent = 1 THEN 1 ELSE 0 END),
            SUM(amount_due)
        FROM tax_delinquencies
    """).fetchone()
    conn.close()

    print(f"\n[trw] === DONE ===")
    print(f"  total delinquent accounts: {inserted:,}")
    print(f"  3+ years delinquent:       {summary[0] or 0:,}")
    print(f"  2 years delinquent:        {summary[1] or 0:,}")
    print(f"  1 year delinquent:         {summary[2] or 0:,}")
    print(f"  total amount owed:         ${summary[3] or 0:,.0f}")


if __name__ == "__main__":
    run()

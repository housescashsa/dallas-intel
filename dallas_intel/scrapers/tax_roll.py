"""
Dallas County Tax Roll (TRW) scraper.

Source: https://www.dallascounty.org/departments/tax/tax-roll.php
Status: ✅ AUTO

The TRW is an ASCII fixed-width file regenerated every Friday and posted
on the following Monday. It contains every property tax account collected
by the Dallas County Tax Office, including delinquent ones.

The page hosts both:
  - A sample file (for testing your parser)
  - The full live TRW file

Field positions are documented in the file's accompanying README on the same
page. Read that README before tweaking the slice positions below — DCTO has
adjusted the layout twice in the last decade.

This script:
  1. Fetches the page and locates the live TRW download link.
  2. Downloads it.
  3. Parses fixed-width records.
  4. Inserts delinquent accounts into `tax_delinquencies`.

NOTE: Penalty/interest is added April 1 (BPP) / July 1 (real property),
so a "delinquent" record from late January is not yet in collection.
"""
import re
import requests
from datetime import datetime
from urllib.parse import urljoin

from dallas_intel.config import TAX_ROLL_TRW_PAGE, RAW_DIR, USER_AGENT
from dallas_intel.db.init import get_connection


HEADERS = {"User-Agent": USER_AGENT}

# Adjust slices after reading the latest TRW README.
# These are illustrative defaults that match the documented layout circa 2023.
SLICES = {
    "account":     slice(0,   17),
    "tax_year":    slice(17,  21),
    "amount_due":  slice(21,  31),  # implied 2 decimals
    "owner_name":  slice(31,  91),
    "prop_addr":   slice(91, 151),
}


def find_trw_url() -> str:
    r = requests.get(TAX_ROLL_TRW_PAGE, headers=HEADERS, timeout=60)
    r.raise_for_status()
    # Look for a link that contains "TRW" and ends in something downloadable
    matches = re.findall(r'href="([^"]*[Tt][Rr][Ww][^"]*)"', r.text)
    # Filter out the sample file
    candidates = [m for m in matches if "sample" not in m.lower()]
    if not candidates:
        raise RuntimeError("No TRW download link found")
    return urljoin(TAX_ROLL_TRW_PAGE, candidates[0])


def download(url: str):
    print(f"[trw] downloading {url}")
    r = requests.get(url, headers=HEADERS, timeout=600)
    r.raise_for_status()
    fname = url.rsplit("/", 1)[-1] or "trw.txt"
    dest = RAW_DIR / fname
    dest.write_bytes(r.content)
    return dest


def parse_record(line: str):
    try:
        account = line[SLICES["account"]].strip()
        if not account or not account[0].isdigit():
            return None
        year = int(line[SLICES["tax_year"]].strip() or 0)
        amt = int(line[SLICES["amount_due"]].strip() or 0) / 100.0
        return {
            "dcad_account": account,
            "tax_year": year,
            "amount_due": amt,
        }
    except Exception:
        return None


def run():
    url = find_trw_url()
    path = download(url)

    conn = get_connection()
    rows_inserted = 0
    current_year = datetime.now().year
    by_account = {}

    with path.open("r", encoding="latin-1") as f:
        for line in f:
            rec = parse_record(line)
            if not rec or rec["amount_due"] <= 0:
                continue
            by_account.setdefault(rec["dcad_account"], []).append(rec)

    for account, recs in by_account.items():
        years_delinquent = sum(1 for r in recs if r["tax_year"] < current_year)
        for r in recs:
            r["years_delinquent"] = years_delinquent
            r["last_seen"] = datetime.utcnow().isoformat()
            conn.execute("""
                INSERT INTO tax_delinquencies
                    (dcad_account, tax_year, amount_due, years_delinquent, last_seen)
                VALUES (:dcad_account, :tax_year, :amount_due, :years_delinquent, :last_seen)
            """, r)
            rows_inserted += 1

    conn.commit()
    conn.close()
    print(f"[trw] {rows_inserted} delinquent rows across {len(by_account)} accounts")


if __name__ == "__main__":
    run()

"""
DCAD bulk parcel scraper — 3-pass join across ACCOUNT_INFO + ACCOUNT_APPRL_YEAR + RES_DETAIL.
Status: AUTO

The ZIP filename ("DCAD2022_CURRENT.ZIP") is misleading — DCAD reuses filenames
and refreshes the data inside. Inspect the dates on the CSVs to confirm currency.
"""
import re
import zipfile
import io
import csv
import requests
from datetime import datetime
from urllib.parse import urljoin

from dallas_intel.config import DCAD_DATA_PRODUCTS, RAW_DIR, USER_AGENT
from dallas_intel.db.init import get_connection
from dallas_intel.scrapers._utils import normalize_name, is_llc_owner

HEADERS = {"User-Agent": USER_AGENT}


def find_latest_zip_url():
    r = requests.get(DCAD_DATA_PRODUCTS, headers=HEADERS, timeout=60)
    r.raise_for_status()
    matches = re.findall(r'href="([^"]+\.[Zz][Ii][Pp])"', r.text)
    bulk = [
        m for m in matches
        if re.search(r"DCAD\d{4}_CURRENT\.zip", m, re.IGNORECASE)
        and "BPP" not in m.upper()
    ]
    if not bulk:
        raise RuntimeError(f"No DCADYYYY_CURRENT.ZIP found. Saw: {matches}")
    def year_of(url):
        m = re.search(r"DCAD(\d{4})_CURRENT", url, re.IGNORECASE)
        return int(m.group(1)) if m else 0
    bulk.sort(key=year_of, reverse=True)
    return urljoin(DCAD_DATA_PRODUCTS, bulk[0])


def download(url, dest):
    print(f"[dcad] downloading {url}")
    with requests.get(url, headers=HEADERS, stream=True, timeout=600) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        seen = 0
        with dest.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 16):
                f.write(chunk)
                seen += len(chunk)
                if total:
                    pct = seen * 100 // total
                    print(f"\r[dcad]   {pct}% ({seen >> 20} / {total >> 20} MB)", end="")
        print()


def safe_int(v):
    if v is None or v == "":
        return 0
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return 0


def safe_str(v):
    return (v or "").strip() if v is not None else ""


def build_property_address(row):
    parts = [safe_str(row.get(k)) for k in ("STREET_NUM", "STREET_HALF_NUM", "FULL_STREET_NAME")]
    return " ".join(p for p in parts if p).strip()


def build_mailing_address(row):
    street_parts = [safe_str(row.get(f"OWNER_ADDRESS_LINE{i}")) for i in (1, 2, 3, 4)]
    street = " ".join(p for p in street_parts if p)
    city = safe_str(row.get("OWNER_CITY"))
    state = safe_str(row.get("OWNER_STATE"))
    z = safe_str(row.get("OWNER_ZIPCODE"))
    out = f"{street}, {city} {state} {z}".strip(", ").strip()
    return re.sub(r"\s+", " ", out)


def build_legal_desc(row):
    parts = [safe_str(row.get(f"LEGAL{i}")) for i in range(1, 6)]
    return " ".join(p for p in parts if p)


def get_owner_name(row):
    biz = safe_str(row.get("BIZ_NAME"))
    if biz:
        return biz
    n1 = safe_str(row.get("OWNER_NAME1"))
    n2 = safe_str(row.get("OWNER_NAME2"))
    return f"{n1} {n2}".strip() if n2 else n1


def stream_csv(zip_path, name):
    with zipfile.ZipFile(zip_path) as z:
        with z.open(name) as f:
            text = io.TextIOWrapper(f, encoding="latin-1", errors="replace")
            for row in csv.DictReader(text):
                yield row


def pass1_account_info(conn, zip_path):
    print("[dcad] pass 1/3: ACCOUNT_INFO.CSV (owner + address spine)")
    n = 0
    now = datetime.utcnow().isoformat()
    for row in stream_csv(zip_path, "ACCOUNT_INFO.CSV"):
        account = safe_str(row.get("ACCOUNT_NUM"))
        if not account:
            continue
        owner = get_owner_name(row)
        state = safe_str(row.get("OWNER_STATE")).upper()
        out_of_state = 1 if (state and state not in ("TX", "TEXAS")) else 0
        conn.execute("""
            INSERT INTO parcels (
                dcad_account, owner_name, owner_name_norm, mailing_address, property_address,
                city, zip, legal_desc, is_llc_owner, out_of_state_mailing, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(dcad_account) DO UPDATE SET
                owner_name = excluded.owner_name,
                owner_name_norm = excluded.owner_name_norm,
                mailing_address = excluded.mailing_address,
                property_address = excluded.property_address,
                city = excluded.city,
                zip = excluded.zip,
                legal_desc = excluded.legal_desc,
                is_llc_owner = excluded.is_llc_owner,
                out_of_state_mailing = excluded.out_of_state_mailing,
                last_updated = excluded.last_updated
        """, (
            account, owner, normalize_name(owner),
            build_mailing_address(row), build_property_address(row),
            safe_str(row.get("PROPERTY_CITY")), safe_str(row.get("PROPERTY_ZIPCODE")),
            build_legal_desc(row),
            1 if is_llc_owner(owner) else 0, out_of_state, now,
        ))
        n += 1
        if n % 25000 == 0:
            conn.commit()
            print(f"[dcad]   pass 1: {n} rows")
    conn.commit()
    print(f"[dcad] pass 1 done: {n} rows")


def pass2_appraisal(conn, zip_path):
    print("[dcad] pass 2/3: ACCOUNT_APPRL_YEAR.CSV (market value)")
    n = 0
    for row in stream_csv(zip_path, "ACCOUNT_APPRL_YEAR.CSV"):
        account = safe_str(row.get("ACCOUNT_NUM"))
        if not account:
            continue
        conn.execute(
            "UPDATE parcels SET market_value = ? WHERE dcad_account = ?",
            (safe_int(row.get("TOT_VAL")), account),
        )
        n += 1
        if n % 25000 == 0:
            conn.commit()
            print(f"[dcad]   pass 2: {n} rows")
    conn.commit()
    print(f"[dcad] pass 2 done: {n} rows")


def pass3_res_detail(conn, zip_path):
    print("[dcad] pass 3/3: RES_DETAIL.CSV (year built, sqft, beds, baths)")
    n = 0
    for row in stream_csv(zip_path, "RES_DETAIL.CSV"):
        account = safe_str(row.get("ACCOUNT_NUM"))
        if not account:
            continue
        yr = safe_int(row.get("YR_BUILT")) or None
        sqft = safe_int(row.get("TOT_LIVING_AREA_SF")) or safe_int(row.get("TOT_MAIN_SF")) or None
        beds = safe_int(row.get("NUM_BEDROOMS")) or None
        full_b = safe_int(row.get("NUM_FULL_BATHS"))
        half_b = safe_int(row.get("NUM_HALF_BATHS"))
        baths = (full_b + half_b * 0.5) if (full_b or half_b) else None
        conn.execute(
            "UPDATE parcels SET year_built=?, sqft=?, beds=?, baths=? WHERE dcad_account=?",
            (yr, sqft, beds, baths, account),
        )
        n += 1
        if n % 25000 == 0:
            conn.commit()
            print(f"[dcad]   pass 3: {n} rows")
    conn.commit()
    print(f"[dcad] pass 3 done: {n} rows")


def run():
    existing = list(RAW_DIR.glob("*DCAD*CURRENT*.zip"))
    if existing:
        zip_path = existing[0]
        print(f"[dcad] using cached {zip_path.name}")
    else:
        url = find_latest_zip_url()
        zip_path = RAW_DIR / url.rsplit("/", 1)[-1]
        download(url, zip_path)

    conn = get_connection()
    pass1_account_info(conn, zip_path)
    pass2_appraisal(conn, zip_path)
    pass3_res_detail(conn, zip_path)

    total = conn.execute("SELECT COUNT(*) FROM parcels").fetchone()[0]
    with_owner = conn.execute("SELECT COUNT(*) FROM parcels WHERE owner_name != ''").fetchone()[0]
    with_addr = conn.execute("SELECT COUNT(*) FROM parcels WHERE property_address != ''").fetchone()[0]
    llcs = conn.execute("SELECT COUNT(*) FROM parcels WHERE is_llc_owner = 1").fetchone()[0]
    oos = conn.execute("SELECT COUNT(*) FROM parcels WHERE out_of_state_mailing = 1").fetchone()[0]
    print(f"\n[dcad] === DONE ===")
    print(f"  total parcels: {total:,}")
    print(f"  with owner:    {with_owner:,}")
    print(f"  with address:  {with_addr:,}")
    print(f"  LLC owned:     {llcs:,}")
    print(f"  out-of-state:  {oos:,}")
    conn.close()


if __name__ == "__main__":
    run()

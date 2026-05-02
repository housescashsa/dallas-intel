"""
DCAD bulk parcel scraper.

Source: https://www.dallascad.org/dataproducts.aspx
Status: ✅ AUTO

DCAD posts annual snapshots as ZIP files (each is several hundred MB and contains:
  - account_apprl_year.csv  (account + appraisal values + owner name)
  - account_info.csv        (mailing address, exemptions)
  - res_detail.csv          (year built, sqft, beds/baths, etc.)
  - multi_owner.csv         (additional owners)

Each ZIP includes a README with column definitions. Column names changed in 2022
and 2024 — read the README inside the ZIP before mapping fields.

This script:
  1. Discovers the latest ZIP link on the data-products page.
  2. Downloads it (~300MB, takes 2–5 min).
  3. Extracts the relevant CSVs.
  4. Normalizes and upserts into the `parcels` table.

To trigger a refresh:
    python -m dallas_intel.scrapers.dcad
"""
import re
import zipfile
import io
import csv
import requests
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin

from dallas_intel.config import DCAD_DATA_PRODUCTS, RAW_DIR, USER_AGENT
from dallas_intel.db.init import get_connection
from dallas_intel.scrapers._utils import normalize_name, is_llc_owner, is_out_of_state


HEADERS = {"User-Agent": USER_AGENT}


def find_latest_zip_url() -> str:
    """Scrape the DCAD data-products page for the most recent appraisal ZIP."""
    r = requests.get(DCAD_DATA_PRODUCTS, headers=HEADERS, timeout=60)
    r.raise_for_status()
    # DCAD typically links files like DCAD2026_CURRENT.ZIP
    matches = re.findall(r'href="([^"]+\.[Zz][Ii][Pp])"', r.text)
    if not matches:
        raise RuntimeError("No ZIP links found on DCAD data products page")
    # Prefer the file with the highest year + 'CURRENT'
    matches.sort(reverse=True)
    return urljoin(DCAD_DATA_PRODUCTS, matches[0])


def download(url: str, dest: Path):
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


def parse_account_csv(content: bytes):
    """
    Yields dicts. Column names vary by year — adapt this mapping after reading
    the README inside the ZIP for the current year.
    """
    text = content.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        # Common DCAD column variants — pick whichever exists
        account = row.get("ACCOUNT_NUM") or row.get("ACCT_NUM") or row.get("ACCOUNT")
        if not account:
            continue
        yield {
            "dcad_account": account.strip(),
            "owner_name": (row.get("OWNER_NAME1") or row.get("OWNER1") or "").strip(),
            "mailing_address": " ".join(filter(None, [
                row.get("STREET_NUM", ""), row.get("STREET", ""),
                row.get("CITY", ""), row.get("STATE", ""), row.get("ZIPCODE", "")
            ])).strip(),
            "property_address": (row.get("STREET_ADDR") or row.get("PROP_ADDR") or "").strip(),
            "city": (row.get("PROP_CITY") or "DALLAS").strip(),
            "zip": (row.get("PROP_ZIP") or "").strip(),
            "legal_desc": (row.get("LEGAL_LINE1") or row.get("LEGAL") or "").strip(),
            "market_value": int(row.get("TOT_VAL", 0) or 0),
            "is_homestead": 1 if (row.get("HOMESTEAD_FLAG") or "").upper() == "Y" else 0,
        }


def upsert_parcel(conn, p):
    p["owner_name_norm"] = normalize_name(p["owner_name"])
    p["is_llc_owner"] = 1 if is_llc_owner(p["owner_name"]) else 0
    p["out_of_state_mailing"] = 1 if is_out_of_state(p["mailing_address"]) else 0
    p["last_updated"] = datetime.utcnow().isoformat()
    conn.execute("""
        INSERT INTO parcels (
            dcad_account, owner_name, owner_name_norm, mailing_address, property_address,
            city, zip, legal_desc, market_value, is_homestead, is_llc_owner,
            out_of_state_mailing, last_updated
        ) VALUES (
            :dcad_account, :owner_name, :owner_name_norm, :mailing_address, :property_address,
            :city, :zip, :legal_desc, :market_value, :is_homestead, :is_llc_owner,
            :out_of_state_mailing, :last_updated
        )
        ON CONFLICT(dcad_account) DO UPDATE SET
            owner_name = excluded.owner_name,
            owner_name_norm = excluded.owner_name_norm,
            mailing_address = excluded.mailing_address,
            property_address = excluded.property_address,
            market_value = excluded.market_value,
            is_homestead = excluded.is_homestead,
            is_llc_owner = excluded.is_llc_owner,
            out_of_state_mailing = excluded.out_of_state_mailing,
            last_updated = excluded.last_updated
    """, p)


def run():
    url = find_latest_zip_url()
    fname = url.rsplit("/", 1)[-1]
    zip_path = RAW_DIR / fname

    if not zip_path.exists():
        download(url, zip_path)
    else:
        print(f"[dcad] using cached {zip_path}")

    conn = get_connection()
    inserted = 0
    with zipfile.ZipFile(zip_path) as z:
        # Find the account file
        target = None
        for name in z.namelist():
            if "account" in name.lower() and name.lower().endswith(".csv"):
                target = name
                break
        if not target:
            raise RuntimeError(f"No account CSV found in {zip_path}; contents: {z.namelist()}")

        print(f"[dcad] parsing {target}")
        with z.open(target) as f:
            content = f.read()
            for parcel in parse_account_csv(content):
                upsert_parcel(conn, parcel)
                inserted += 1
                if inserted % 5000 == 0:
                    conn.commit()
                    print(f"[dcad]   {inserted} parcels...")
    conn.commit()
    conn.close()
    print(f"[dcad] done. {inserted} parcels upserted.")


if __name__ == "__main__":
    run()

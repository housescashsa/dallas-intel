"""
Dallas 311 / Code violations scraper.

Source: https://www.dallasopendata.com (Socrata API)
Dataset: 311 Service Requests (current FY) — id: gc4d-8a49
Status: ✅ AUTO

The City of Dallas exposes 311 service requests through Socrata's SODA REST
API. We filter to the violation types that signal motivated sellers:
  - High weeds & grass
  - Junk motor vehicle
  - Substandard structure
  - Open & vacant building
  - Demolition (substandard)
  - Litter
  - Dumping

Socrata supports SoQL ($where, $limit, $offset, $select, $order). Free tier
allows ~1000 requests/hour without an app token; with a token, 10k+/hour.
Get a token at https://dev.socrata.com/foundry/www.dallasopendata.com/gc4d-8a49

Set env var: DALLAS_SODA_TOKEN
"""
import os
import requests
from datetime import datetime, timedelta

from dallas_intel.config import DALLAS_OPEN_DATA, SODA_311_DATASET, USER_AGENT
from dallas_intel.db.init import get_connection


HEADERS = {
    "User-Agent": USER_AGENT,
    "X-App-Token": os.environ.get("DALLAS_SODA_TOKEN", ""),
}

MOTIVATED_SELLER_VIOLATIONS = [
    "High Weeds and Grass",
    "Junk Motor Vehicle",
    "Substandard Structure",
    "Open and Vacant Building",
    "Demolition",
    "Litter",
    "Illegal Dumping",
    "Code Concern",
]

PAGE_SIZE = 5000


def run(days_back: int = 30):
    cutoff = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%dT00:00:00")

    # Quote violation types for SoQL
    types_clause = " OR ".join([f"service_request_type = '{v}'" for v in MOTIVATED_SELLER_VIOLATIONS])
    where = f"created_date >= '{cutoff}' AND ({types_clause})"

    base = f"{DALLAS_OPEN_DATA}/resource/{SODA_311_DATASET}.json"
    conn = get_connection()
    inserted = 0
    offset = 0

    while True:
        params = {
            "$where": where,
            "$limit": PAGE_SIZE,
            "$offset": offset,
            "$order": "created_date DESC",
        }
        r = requests.get(base, params=params, headers=HEADERS, timeout=120)
        r.raise_for_status()
        rows = r.json()
        if not rows:
            break

        for row in rows:
            sr = row.get("service_request_number") or row.get("sr_number")
            if not sr:
                continue
            conn.execute("""
                INSERT OR IGNORE INTO code_violations
                    (sr_number, address, violation_type, status, open_date,
                     close_date, council_district, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sr,
                row.get("street_address") or row.get("address"),
                row.get("service_request_type"),
                row.get("status"),
                row.get("created_date"),
                row.get("closed_date"),
                row.get("council_district"),
                datetime.utcnow().isoformat(),
            ))
            inserted += 1

        print(f"[311]   {inserted} rows...")
        if len(rows) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    conn.commit()
    conn.close()
    print(f"[311] done. {inserted} violations from last {days_back} days.")


if __name__ == "__main__":
    run()

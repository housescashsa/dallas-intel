"""
Skip-trace CSV exporter.

Exports leads in a format that uploads cleanly to:
  - BatchSkipTracing
  - REISkip
  - Skip Genie
  - Most other skip-trace vendors (column names align with their import templates)

USAGE:
    python -m dallas_intel.exports.skiptrace --score-min 70 --out leads.csv
"""
import argparse
import csv
import json
from pathlib import Path

from dallas_intel.db.init import get_connection


COLUMNS = [
    "first_name", "last_name", "full_name",
    "property_address", "property_city", "property_state", "property_zip",
    "mailing_address", "apn", "lead_score", "lead_type",
]


def split_name(full):
    """Best-effort first/last split. Skip-trace services prefer separate fields."""
    if not full or " " not in full:
        return "", full or ""
    parts = full.replace(",", "").split()
    # Strip estate prefixes
    if parts[0].upper() in {"ESTATE", "THE"}:
        return "", full
    if len(parts) >= 2:
        return parts[0], parts[-1]
    return "", full


def run(score_min: int, out_path: Path, lead_types=None):
    conn = get_connection()
    sql = "SELECT * FROM leads WHERE score >= ?"
    args = [score_min]
    if lead_types:
        placeholders = ",".join("?" * len(lead_types))
        sql += f" AND lead_type IN ({placeholders})"
        args.extend(lead_types)
    sql += " ORDER BY score DESC"
    rows = conn.execute(sql, args).fetchall()

    with out_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            first, last = split_name(r["owner_name"])
            w.writerow({
                "first_name": first,
                "last_name": last,
                "full_name": r["owner_name"],
                "property_address": r["property_address"],
                "property_city": r["city"],
                "property_state": "TX",
                "property_zip": r["zip"],
                "mailing_address": r["mailing_address"],
                "apn": r["dcad_account"],
                "lead_score": r["score"],
                "lead_type": r["lead_type"],
            })
    conn.close()
    print(f"[skiptrace] wrote {len(rows)} leads to {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--score-min", type=int, default=50)
    ap.add_argument("--out", type=Path, default=Path("skiptrace.csv"))
    ap.add_argument("--types", default="", help="Comma-separated lead types")
    args = ap.parse_args()
    types = [t.strip() for t in args.types.split(",") if t.strip()]
    run(args.score_min, args.out, types or None)


if __name__ == "__main__":
    main()

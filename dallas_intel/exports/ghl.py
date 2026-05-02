"""
GoHighLevel CSV exporter.

GHL accepts contact imports with a fixed schema. Tags are pipe-delimited.
Set every lead's Source = "Dallas Property Intel" so you can build a
Smart List and route them through your pipeline.

USAGE:
    python -m dallas_intel.exports.ghl --score-min 50 --out ghl_upload.csv
"""
import argparse
import csv
import json
from pathlib import Path

from dallas_intel.db.init import get_connection


COLUMNS = [
    "Contact Name", "First Name", "Last Name", "Email", "Phone",
    "Address 1", "City", "State", "Postal Code",
    "Source", "Tags", "Mailing Address",
    "Lead Score", "Lead Type", "DCAD Account",
    "Doc Number", "Filed Date",
]


def run(score_min: int, out_path: Path, lead_types=None, tag_prefix="DallasIntel"):
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
            flags = json.loads(r["flags"] or "[]")
            tag_score = "Hot" if r["score"] >= 70 else ("Warm" if r["score"] >= 50 else "Active")
            tags = "|".join([
                tag_prefix,
                f"{tag_prefix}-{tag_score}",
                f"{tag_prefix}-{r['lead_type']}",
                *flags,
            ])
            w.writerow({
                "Contact Name": r["owner_name"],
                "First Name": "",
                "Last Name": "",
                "Email": "",
                "Phone": "",
                "Address 1": r["property_address"],
                "City": r["city"],
                "State": "TX",
                "Postal Code": r["zip"],
                "Source": "Dallas Property Intel",
                "Tags": tags,
                "Mailing Address": r["mailing_address"],
                "Lead Score": r["score"],
                "Lead Type": r["lead_type"],
                "DCAD Account": r["dcad_account"],
                "Doc Number": r["doc_number"],
                "Filed Date": r["filed_date"],
            })
    conn.close()
    print(f"[ghl] wrote {len(rows)} leads to {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--score-min", type=int, default=50)
    ap.add_argument("--out", type=Path, default=Path("ghl_upload.csv"))
    ap.add_argument("--types", default="")
    args = ap.parse_args()
    types = [t.strip() for t in args.types.split(",") if t.strip()]
    run(args.score_min, args.out, types or None)


if __name__ == "__main__":
    main()

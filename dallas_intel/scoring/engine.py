"""
Scoring engine.

Walks every source table (recordings, court_filings, code_violations,
tax_delinquencies, tax_sales), joins to the parcel spine via DCAD account
or fuzzy owner/address match, derives flags, scores, and writes the
unified `leads` table that the dashboard reads.

Run AFTER all scrapers complete:
    python -m dallas_intel.scoring.engine
"""
import json
from datetime import datetime

from dallas_intel.db.init import get_connection
from dallas_intel.scoring.weights import score_flags


# Map recording doc-type -> high-level lead type and seed flags
RECORDING_MAP = {
    "LIS PENDENS":            ("LIS PENDENS",  ["Lis Pendens"]),
    "SUBSTITUTE TRUSTEE":     ("FORECLOSURE",  ["Substitute Trustee Notice", "Pre-Foreclosure"]),
    "FEDERAL TAX LIEN":       ("LIEN",         ["State Tax Lien"]),
    "STATE TAX LIEN":         ("LIEN",         ["State Tax Lien"]),
    "TAX LIEN":               ("LIEN",         ["State Tax Lien"]),
    "MECHANIC'S LIEN":        ("LIEN",         ["Mechanic's Lien"]),
    "MECHANICS LIEN":         ("LIEN",         ["Mechanic's Lien"]),
    "HOSPITAL LIEN":          ("LIEN",         ["State Tax Lien"]),
    "HOA LIEN":               ("LIEN",         ["HOA Lien"]),
    "AFFIDAVIT OF HEIRSHIP":  ("PROBATE",      ["Heirship", "Family Transfer"]),
    "QUITCLAIM DEED":         ("QUITCLAIM",    ["Recent Quitclaim"]),
    "ABSTRACT OF JUDGMENT":   ("JUDGMENT",     []),
}

COURT_MAP = {
    "PROBATE":  ("PROBATE",  ["Probate", "Estate"]),
    "DIVORCE":  ("DIVORCE",  ["Divorce Pending"]),
    "EVICTION": ("EVICTION", ["Eviction Filed", "Landlord"]),
    "CIVIL":    ("LIEN",     []),
}


def derive_parcel_flags(parcel):
    flags = []
    if parcel["is_homestead"]:
        flags.append("Homestead")
        flags.append("Owner Occupied")
    else:
        flags.append("No Homestead")
    if parcel["is_llc_owner"]:
        flags.append("LLC Owner")
    if parcel["out_of_state_mailing"]:
        flags.append("Out-of-State Mailing")
    if parcel["year_built"] and parcel["year_built"] < 1970:
        flags.append("Pre-1970 Build")
    return flags


def build_leads():
    conn = get_connection()
    conn.execute("DELETE FROM leads")  # full rebuild every run

    # ---- Recordings ----
    cur = conn.execute("""
        SELECT r.*, p.property_address, p.city, p.zip, p.mailing_address,
               p.owner_name, p.is_homestead, p.is_llc_owner, p.out_of_state_mailing,
               p.year_built, p.dcad_account AS parcel_account
        FROM recordings r
        LEFT JOIN parcels p
          ON p.owner_name_norm = r.grantor_norm
          OR p.dcad_account = r.dcad_account
    """)
    inserted = 0
    for row in cur.fetchall():
        doc_type = (row["doc_type"] or "").upper()
        mapping = RECORDING_MAP.get(doc_type)
        if not mapping:
            continue
        lead_type, seed = mapping
        parcel = {k: row[k] for k in row.keys()}
        flags = list(seed) + derive_parcel_flags(parcel)
        score = score_flags(flags)
        conn.execute("""
            INSERT OR REPLACE INTO leads
                (dcad_account, lead_type, score, flags, doc_number, filed_date,
                 owner_name, property_address, city, zip, mailing_address,
                 amount, legal_desc, source_url, last_scored)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row["parcel_account"], lead_type, score, json.dumps(flags),
            row["doc_number"], row["filed_date"], row["grantor"],
            row["property_address"], row["city"], row["zip"], row["mailing_address"],
            row["amount"], row["legal_desc"], row["source_url"],
            datetime.utcnow().isoformat(),
        ))
        inserted += 1

    # ---- Court filings ----
    cur = conn.execute("""
        SELECT c.*, p.property_address, p.city, p.zip, p.mailing_address,
               p.owner_name, p.is_homestead, p.is_llc_owner, p.out_of_state_mailing,
               p.year_built, p.dcad_account AS parcel_account
        FROM court_filings c
        LEFT JOIN parcels p ON p.owner_name_norm = c.party_name_norm
    """)
    for row in cur.fetchall():
        mapping = COURT_MAP.get((row["case_type"] or "").upper())
        if not mapping:
            continue
        lead_type, seed = mapping
        parcel = {k: row[k] for k in row.keys()}
        flags = list(seed) + derive_parcel_flags(parcel)
        score = score_flags(flags)
        conn.execute("""
            INSERT OR REPLACE INTO leads
                (dcad_account, lead_type, score, flags, doc_number, filed_date,
                 owner_name, property_address, city, zip, mailing_address,
                 amount, legal_desc, source_url, last_scored)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row["parcel_account"], lead_type, score, json.dumps(flags),
            row["case_number"], row["filed_date"], row["party_name"],
            row["property_address"], row["city"], row["zip"], row["mailing_address"],
            None, None, row["source_url"],
            datetime.utcnow().isoformat(),
        ))
        inserted += 1

    # ---- Code violations ----
    cur = conn.execute("""
        SELECT v.*, p.dcad_account AS parcel_account, p.property_address AS prop_addr,
               p.city, p.zip, p.mailing_address, p.owner_name, p.is_homestead,
               p.is_llc_owner, p.out_of_state_mailing, p.year_built
        FROM code_violations v
        LEFT JOIN parcels p ON UPPER(p.property_address) = UPPER(v.address)
    """)
    # Aggregate by address: count violations per parcel
    by_parcel = {}
    for row in cur.fetchall():
        key = row["parcel_account"] or row["address"]
        by_parcel.setdefault(key, {"row": row, "count": 0, "vtypes": set()})
        by_parcel[key]["count"] += 1
        by_parcel[key]["vtypes"].add(row["violation_type"])

    for key, data in by_parcel.items():
        row = data["row"]
        n = data["count"]
        vtypes = data["vtypes"]
        flags = []
        if "Substandard Structure" in vtypes:
            flags.append("Substandard Structure")
        if "Open and Vacant Building" in vtypes:
            flags.append("Open & Vacant")
        if "Demolition" in vtypes:
            flags.append("Demo Lien")
        if "High Weeds and Grass" in vtypes:
            flags.append("High Weeds")
        if "Junk Motor Vehicle" in vtypes:
            flags.append("Junk Vehicle")
        if n >= 4:
            flags.append("Code Violation x4")
        elif n >= 2:
            flags.append("Code Violation x2")
        parcel = {k: row[k] for k in row.keys()}
        flags += derive_parcel_flags(parcel)
        score = score_flags(flags)
        conn.execute("""
            INSERT OR REPLACE INTO leads
                (dcad_account, lead_type, score, flags, doc_number, filed_date,
                 owner_name, property_address, city, zip, mailing_address,
                 amount, legal_desc, source_url, last_scored)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row["parcel_account"], "CODE", score, json.dumps(flags),
            row["sr_number"], row["open_date"], row["owner_name"],
            row["prop_addr"] or row["address"], row["city"], row["zip"],
            row["mailing_address"], None, None,
            "https://www.dallasopendata.com",
            datetime.utcnow().isoformat(),
        ))
        inserted += 1

    # ---- Tax delinquencies ----
    cur = conn.execute("""
        SELECT t.dcad_account, t.years_delinquent, SUM(t.amount_due) AS total_due,
               p.owner_name, p.property_address, p.city, p.zip, p.mailing_address,
               p.is_homestead, p.is_llc_owner, p.out_of_state_mailing, p.year_built
        FROM tax_delinquencies t
        LEFT JOIN parcels p ON p.dcad_account = t.dcad_account
        GROUP BY t.dcad_account
    """)
    for row in cur.fetchall():
        years = row["years_delinquent"] or 1
        flags = []
        if years >= 3:
            flags.append("Tax Delinquent 3yr")
        elif years == 2:
            flags.append("Tax Delinquent 2yr")
        else:
            flags.append("Tax Delinquent 1yr")
        parcel = {k: row[k] for k in row.keys()}
        flags += derive_parcel_flags(parcel)
        score = score_flags(flags)
        conn.execute("""
            INSERT OR REPLACE INTO leads
                (dcad_account, lead_type, score, flags, doc_number, filed_date,
                 owner_name, property_address, city, zip, mailing_address,
                 amount, legal_desc, source_url, last_scored)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row["dcad_account"], "TAX", score, json.dumps(flags),
            f"TAX-{years}YR", None, row["owner_name"],
            row["property_address"], row["city"], row["zip"], row["mailing_address"],
            row["total_due"], None,
            "https://www.dallascounty.org/departments/tax/tax-roll.php",
            datetime.utcnow().isoformat(),
        ))
        inserted += 1

    conn.commit()
    conn.close()
    print(f"[score] built {inserted} leads")


if __name__ == "__main__":
    build_leads()

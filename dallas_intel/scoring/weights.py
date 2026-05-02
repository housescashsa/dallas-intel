"""
Scoring weights for motivated-seller signals.
Mirror the SCORE_WEIGHTS object in the React dashboard.
Tune these as you learn what converts in your own deals.
"""
SCORE_WEIGHTS = {
    # Foreclosure & litigation (highest)
    "Lis Pendens": 25,
    "Substitute Trustee Notice": 25,
    "Pre-Foreclosure": 10,
    "Auction Imminent": 8,

    # Tax delinquency
    "Tax Delinquent 3yr": 25,
    "Tax Delinquent 2yr": 18,
    "Tax Delinquent 1yr": 10,

    # Code & condition
    "Substandard Structure": 22,
    "Open & Vacant": 18,
    "Demo Lien": 20,
    "Code Violation x4": 18,
    "Code Violation x2": 10,
    "Vacant Indicator": 12,
    "High Weeds": 4,
    "Junk Vehicle": 4,

    # Probate & estate
    "Probate": 22,
    "Estate": 18,
    "Heirs Filed": 15,
    "Heirship": 8,

    # Owner distress / entity
    "Forfeited Entity": 15,
    "Out-of-State LLC": 12,
    "Out-of-State Mailing": 10,
    "Mechanic's Lien": 12,
    "HOA Lien": 8,
    "State Tax Lien": 10,
    "LLC Owner": 4,

    # Life events
    "Divorce Pending": 14,
    "Eviction Filed": 12,
    "Landlord": 6,
    "Rental Property": 4,

    # Other transfers
    "Recent Quitclaim": 8,
    "Family Transfer": 6,

    # Mild
    "1942 Build": 4,
    "Pre-1970 Build": 4,
    "No Homestead": 6,

    # Negative / neutral
    "Owner Occupied": 0,
    "Homestead": 0,
    "Joint Owners": 0,
    "Solo Owner": 0,
}


def score_flags(flags):
    return min(100, sum(SCORE_WEIGHTS.get(f, 0) for f in flags))

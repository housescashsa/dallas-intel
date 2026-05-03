"""
Scoring weights for motivated-seller signals.
Tuned for Dallas County tax-delinquency-driven workflow.
Max score = 100.
"""
SCORE_WEIGHTS = {
    # Tax delinquency — primary signal in Dallas
    "Tax Delinquent 3yr": 35,
    "Tax Delinquent 2yr": 22,
    "Tax Delinquent 1yr": 10,

    # Foreclosure & litigation (when OPR feeds in)
    "Lis Pendens": 30,
    "Substitute Trustee Notice": 30,
    "Pre-Foreclosure": 12,
    "Auction Imminent": 10,

    # Code & condition
    "Substandard Structure": 25,
    "Open & Vacant": 22,
    "Demo Lien": 22,
    "Code Violation x4": 18,
    "Code Violation x2": 10,
    "Vacant Indicator": 14,
    "High Weeds": 5,
    "Junk Vehicle": 5,

    # Probate & estate
    "Probate": 25,
    "Estate": 20,
    "Heirs Filed": 17,
    "Heirship": 10,

    # Owner distress / entity
    "Forfeited Entity": 18,
    "Out-of-State LLC": 14,
    "Out-of-State Mailing": 12,
    "Mechanic's Lien": 13,
    "HOA Lien": 9,
    "State Tax Lien": 11,
    "LLC Owner": 6,

    # Life events
    "Divorce Pending": 16,
    "Eviction Filed": 14,
    "Landlord": 7,
    "Rental Property": 5,

    # Other transfers
    "Recent Quitclaim": 9,
    "Family Transfer": 7,

    # Mild signals
    "Pre-1970 Build": 6,
    "1942 Build": 6,
    "No Homestead": 8,

    # Neutral / negative
    "Owner Occupied": 0,
    "Homestead": 0,
    "Joint Owners": 0,
    "Solo Owner": 0,
}


def score_flags(flags):
    return min(100, sum(SCORE_WEIGHTS.get(f, 0) for f in flags))

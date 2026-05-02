# Dallas Property Intel

Motivated-seller lead engine for Dallas County, Texas. Pulls public records from every
automatable source, scores each lead, and exports to GHL or skip-trace CSV.

## Quick start

```bash
git clone <your-repo-url>
cd dallas_intel
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium  # only needed for the JS-rendered sources

# Initialize the SQLite database
python -m dallas_intel.db.init

# Run scrapers (each can be run independently)
python -m dallas_intel.scrapers.dcad           # Master parcel/owner table
python -m dallas_intel.scrapers.tax_roll       # Delinquent accounts (Friday weekly)
python -m dallas_intel.scrapers.code_311       # Dallas 311/code violations (Socrata API)
python -m dallas_intel.scrapers.lgbs_tax_sale  # Upcoming tax-sale list
python -m dallas_intel.scrapers.opr            # County Clerk recordings (Playwright)
python -m dallas_intel.scrapers.courts_portal  # Probate / divorce / eviction (Playwright)

# Score everything in the database
python -m dallas_intel.scoring.engine

# Export
python -m dallas_intel.exports.ghl --score-min 50
python -m dallas_intel.exports.skiptrace --score-min 70
```

## Source automation status

| # | Source | Status | Notes |
|---|--------|--------|-------|
| 1 | DCAD bulk parcel/owner data | ✅ AUTO | ZIP download, no auth |
| 2 | Dallas County Tax Roll (TRW) | ✅ AUTO | Updated Fridays, ASCII |
| 3 | Dallas Open Data 311/code | ✅ AUTO | Socrata REST API |
| 4 | LGBS tax-sale upcoming list | ✅ AUTO | HTML GET |
| 5 | County Clerk OPR (Kofile) | ⚠️ SEMI | JS-rendered; Playwright; rate-limited |
| 6 | Dallas Courts Portal (probate, civil, JP) | ⚠️ SEMI | JS-rendered; Playwright; aggressive rate limit |
| 7 | RealAuction sheriff-sale | 🛑 MANUAL | Requires verified account + $1,000 deposit |
| 8 | PACER bankruptcy filings | 🛑 MANUAL | Paid account; per-page fees |
| 9 | Daily Commercial Record | 🛑 MANUAL | Paid subscription |
| 10 | Foreclosure notices (PDF) | ⚠️ SEMI | OCR; ~85% success on scanned ones |
| 11 | TX Secretary of State entity status | ✅ AUTO | Stub here, plug into your enrichment |
| 12 | Suburb code portals (Garland/Mesquite/etc.) | ⚠️ SEMI | Each city uses a different vendor |
| 13 | HUD USPS vacancy data | ✅ AUTO | Quarterly file |
| 14 | Skip tracing | 🛑 MANUAL | Use BatchSkipTracing/REISkip/PropStream |

See `docs/manual_processes.md` for step-by-step on each of the 🛑 items.

## Repo layout

```
dallas_intel/
├── dallas_intel/
│   ├── __init__.py
│   ├── config.py            # Centralized URLs and constants
│   ├── db/
│   │   ├── __init__.py
│   │   ├── init.py          # Creates SQLite schema
│   │   └── schema.sql
│   ├── scrapers/
│   │   ├── __init__.py
│   │   ├── dcad.py          # ✅ AUTO
│   │   ├── tax_roll.py      # ✅ AUTO
│   │   ├── code_311.py      # ✅ AUTO
│   │   ├── lgbs_tax_sale.py # ✅ AUTO
│   │   ├── opr.py           # ⚠️ Playwright
│   │   └── courts_portal.py # ⚠️ Playwright
│   ├── scoring/
│   │   ├── __init__.py
│   │   ├── weights.py
│   │   └── engine.py
│   └── exports/
│       ├── __init__.py
│       ├── ghl.py
│       └── skiptrace.py
├── docs/
│   └── manual_processes.md
├── requirements.txt
├── .gitignore
└── README.md
```

## Legend

- ✅ AUTO — fully scripted, no human input after initial config
- ⚠️ SEMI — automated but fragile (JS rendering, rate limits, OCR)
- 🛑 MANUAL — must be done by you; instructions in `docs/manual_processes.md`

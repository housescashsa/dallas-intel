#!/bin/bash
# Master pipeline — runs all scrapers + scoring + exports
set -e
cd "$(dirname "$0")"
source .venv/bin/activate

LOG="data/pipeline.log"
mkdir -p data
echo "============================================" >> "$LOG"
echo "RUN STARTED: $(date)" >> "$LOG"
echo "============================================" >> "$LOG"

# Fast scrapers first (they finish in seconds)
python -m dallas_intel.scrapers.code_311 >> "$LOG" 2>&1 || echo "311 failed" >> "$LOG"
python -m dallas_intel.scrapers.lgbs_tax_sale >> "$LOG" 2>&1 || echo "LGBS failed" >> "$LOG"

# TRW — uses cached zip during the day, re-downloads weekly
python -m dallas_intel.scrapers.tax_roll >> "$LOG" 2>&1 || echo "TRW failed" >> "$LOG"

# Score everything
python -m dallas_intel.scoring.engine >> "$LOG" 2>&1

# Refresh exports
python -m dallas_intel.exports.skiptrace --score-min 50 --out data/hot_leads_skiptrace.csv >> "$LOG" 2>&1
python -m dallas_intel.exports.ghl --score-min 50 --out data/hot_leads_ghl.csv >> "$LOG" 2>&1
python -m dallas_intel.exports.skiptrace --score-min 30 --out data/active_leads_skiptrace.csv >> "$LOG" 2>&1
python -m dallas_intel.exports.ghl --score-min 30 --out data/active_leads_ghl.csv >> "$LOG" 2>&1

echo "RUN FINISHED: $(date)" >> "$LOG"
echo "" >> "$LOG"

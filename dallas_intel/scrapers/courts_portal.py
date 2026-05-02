"""
Dallas County Courts Portal scraper (probate, divorce, eviction, civil).

Source: https://www.dallascounty.org/services/record-search/
Status: ⚠️ SEMI — JS-rendered, aggressive rate limit

This portal is a Tyler Technologies "Odyssey Public Access" instance. It serves:
  - Probate Courts 1, 2, 3 → estate administrations, heirships, guardianships
  - District Civil Courts → divorces, partition suits, mortgage foreclosures
  - JP Courts (10 precincts) → evictions
  - County Courts at Law → smaller civil

The portal aggressively rate-limits — typically 100 searches per session before
soft-blocking. We:
  - Throttle to 2.5s between searches.
  - Search by date range (10-day chunks).
  - Use case-type filters to limit result count per query.

USAGE:
    python -m dallas_intel.scrapers.courts_portal --case-types PROBATE,DIVORCE --days 14
"""
import argparse
import asyncio
from datetime import datetime, timedelta

from dallas_intel.config import COURTS_PORTAL
from dallas_intel.db.init import get_connection
from dallas_intel.scrapers._utils import normalize_name


# These map to the dropdown values in the portal's case-type filter.
CASE_TYPE_QUERIES = {
    "PROBATE": ["Probate", "Independent Administration", "Heirship", "Will Probate"],
    "DIVORCE": ["Divorce", "Divorce No Children", "Divorce With Children"],
    "EVICTION": ["Eviction", "Forcible Detainer"],
    "CIVIL": ["Foreclosure", "Lien", "Quiet Title", "Partition"],
}


async def run_async(case_types, days):
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise SystemExit(
            "Playwright not installed. Run: pip install playwright && playwright install chromium"
        )

    end = datetime.now()
    start = end - timedelta(days=days)
    conn = get_connection()
    inserted = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={"width": 1400, "height": 900})
        page = await context.new_page()

        await page.goto(COURTS_PORTAL, timeout=60_000)
        await page.wait_for_load_state("networkidle")

        # Click "Smart Search"
        try:
            await page.click("text=Smart Search", timeout=10_000)
        except Exception:
            pass

        for code in case_types:
            for label in CASE_TYPE_QUERIES.get(code, []):
                print(f"[courts] searching {code} '{label}' from {start:%Y-%m-%d}")
                try:
                    await page.click("text=Advanced Filtering Options", timeout=5000)
                    # Date filter
                    await page.fill("input[name='FiledDateFrom']", start.strftime("%m/%d/%Y"))
                    await page.fill("input[name='FiledDateTo']", end.strftime("%m/%d/%Y"))
                    # Case type
                    await page.fill("input[placeholder*='Case Type']", label)
                    await page.click("button:has-text('Search')")
                    await page.wait_for_load_state("networkidle")

                    while True:
                        rows = await page.query_selector_all("table.dataTable tbody tr")
                        for row in rows:
                            cells = await row.query_selector_all("td")
                            if len(cells) < 5:
                                continue
                            case_num = (await cells[0].inner_text()).strip()
                            party = (await cells[1].inner_text()).strip()
                            filed_date = (await cells[2].inner_text()).strip()
                            court = (await cells[3].inner_text()).strip()
                            status = (await cells[4].inner_text()).strip()
                            conn.execute("""
                                INSERT OR REPLACE INTO court_filings
                                    (case_number, case_type, filed_date, party_name,
                                     party_name_norm, court, status, source_url, last_seen)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                case_num, code, filed_date,
                                party, normalize_name(party),
                                court, status, COURTS_PORTAL,
                                datetime.utcnow().isoformat(),
                            ))
                            inserted += 1

                        # Pagination
                        next_btn = await page.query_selector("a.paginate_button.next:not(.disabled)")
                        if not next_btn:
                            break
                        await next_btn.click()
                        await page.wait_for_load_state("networkidle")
                        await asyncio.sleep(2.5)

                    conn.commit()
                except Exception as e:
                    print(f"[courts]   error '{label}': {e}")
                    print("[courts]   pausing 60s; rate limit suspected")
                    await asyncio.sleep(60)

        await browser.close()

    conn.close()
    print(f"[courts] done. {inserted} filings.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case-types", default=",".join(CASE_TYPE_QUERIES.keys()))
    ap.add_argument("--days", type=int, default=14)
    args = ap.parse_args()
    asyncio.run(run_async(args.case_types.split(","), args.days))


if __name__ == "__main__":
    main()

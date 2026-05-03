"""
Dallas County Clerk Official Public Records scraper.
Source: https://dallas.tx.publicsearch.us/search/advanced
Status: SEMI — Playwright; rate-limited; sometimes captchas

Selectors verified via diagnose_opr.py:
  - #recordedDateRange-start / -end  (date inputs, MM/DD/YYYY)
  - #docTypes-input                  (typeahead doc-type filter)
  - text=Search                      (submit)
  - text=Clear                       (reset)
"""
import argparse
import asyncio
import re
from datetime import datetime, timedelta

from dallas_intel.config import OPR_PUBLICSEARCH
from dallas_intel.db.init import get_connection
from dallas_intel.scrapers._utils import normalize_name


ADVANCED_URL = "https://dallas.tx.publicsearch.us/search/advanced"

# These are the EXACT labels the doc-type typeahead expects.
# Add/remove based on what shows up when you type in the field manually.
DOC_TYPE_LABELS = {
    "LIS_PENDENS":         ["Lis Pendens"],
    "SUBSTITUTE_TRUSTEE":  ["Substitute Trustee", "Notice of Trustee Sale"],
    "FEDERAL_TAX_LIEN":    ["Federal Tax Lien"],
    "STATE_TAX_LIEN":      ["State Tax Lien"],
    "MECHANICS_LIEN":      ["Mechanic's Lien"],
    "HOSPITAL_LIEN":       ["Hospital Lien"],
    "HOA_LIEN":            ["HOA Lien", "Homeowners Association Lien"],
    "AFFIDAVIT_HEIRSHIP":  ["Affidavit of Heirship"],
    "QUITCLAIM":           ["Quitclaim Deed"],
    "ABSTRACT_JUDGMENT":   ["Abstract of Judgment"],
}

RATE_LIMIT_S = 2.5


async def dismiss_overlays(page):
    for txt in ("OK", "Continue", "I Accept", "Accept", "Got it"):
        try:
            await page.click(f"text={txt}", timeout=1500)
            await asyncio.sleep(0.5)
        except Exception:
            pass


async def fresh_search_page(page):
    """Reset the form by reloading."""
    await page.goto(ADVANCED_URL, timeout=60_000)
    await page.wait_for_load_state("networkidle")
    await dismiss_overlays(page)
    await page.wait_for_selector("#docTypes-input", timeout=15_000)


async def run_one_search(page, label, start, end):
    """Run a single doc-type search; returns list of result dicts."""
    await fresh_search_page(page)

    # Set date range
    await page.fill("#recordedDateRange-start", start.strftime("%m/%d/%Y"))
    await page.fill("#recordedDateRange-end", end.strftime("%m/%d/%Y"))

    # Set doc type via typeahead
    await page.click("#docTypes-input")
    await page.fill("#docTypes-input", label)
    await asyncio.sleep(1.0)  # let typeahead populate
    # Click the first matching dropdown option
    try:
        await page.click(f"div[role='option']:has-text('{label}')", timeout=5_000)
    except Exception:
        # Fallback: press Enter to accept the first suggestion
        await page.keyboard.press("Enter")
    await asyncio.sleep(0.5)

    # Submit
    await page.click("button:has-text('Search')")

    # Wait for results URL or table; publicsearch routes to /search/results
    try:
        await page.wait_for_url("**/search/results**", timeout=20_000)
    except Exception:
        pass
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(2)

    results = []
    while True:
        # Each result row is a card on this site. Try multiple selectors.
        rows = await page.query_selector_all(
            "[data-testid='result-row'], "
            ".search-results__row, "
            "tr.result-row, "
            "article.result"
        )
        if not rows:
            # Try grabbing all elements that contain a 10+ digit doc number
            rows = await page.query_selector_all("div:has-text('Doc #')")

        for row in rows:
            text = (await row.inner_text()).strip()
            doc_num_match = re.search(r"\b\d{10,15}\b", text)
            date_match = re.search(r"\d{2}/\d{2}/\d{4}", text)
            if not doc_num_match:
                continue
            results.append({
                "doc_number": doc_num_match.group(0),
                "filed_date": date_match.group(0) if date_match else None,
                "raw": text[:500],
            })

        # Pagination
        next_btn = await page.query_selector("button[aria-label='Next page'], button:has-text('Next')")
        if not next_btn:
            break
        disabled = await next_btn.get_attribute("disabled")
        if disabled is not None:
            break
        await next_btn.click()
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(RATE_LIMIT_S)

    return results


async def run_async(doc_types, days):
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise SystemExit("Run: pip install playwright && playwright install chromium")

    end = datetime.now()
    start = end - timedelta(days=days)
    conn = get_connection()
    inserted = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={"width": 1400, "height": 900})
        page = await context.new_page()

        for code in doc_types:
            for label in DOC_TYPE_LABELS.get(code, []):
                print(f"[opr] {code}: '{label}' from {start:%Y-%m-%d} to {end:%Y-%m-%d}")
                try:
                    results = await run_one_search(page, label, start, end)
                    print(f"[opr]   found {len(results)} results")
                    for rec in results:
                        # Try to extract grantor: usually the all-caps line above the doc number
                        grantor_match = re.search(r"([A-Z][A-Z &',.\-]{3,60})", rec["raw"])
                        grantor = grantor_match.group(1).strip() if grantor_match else ""
                        conn.execute("""
                            INSERT OR REPLACE INTO recordings
                                (doc_number, doc_type, filed_date, grantor, grantor_norm,
                                 legal_desc, source_url, raw_blob, last_seen)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            rec["doc_number"], label.upper(), rec["filed_date"],
                            grantor, normalize_name(grantor), None,
                            ADVANCED_URL, rec["raw"], datetime.utcnow().isoformat(),
                        ))
                        inserted += 1
                    conn.commit()
                except Exception as e:
                    print(f"[opr]   ERROR: {e}")
                    print("[opr]   pausing 20s — check browser for captcha")
                    await asyncio.sleep(20)
                await asyncio.sleep(RATE_LIMIT_S)

        await browser.close()
    conn.close()
    print(f"\n[opr] === DONE === {inserted} recordings ingested")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc-types", default=",".join(DOC_TYPE_LABELS.keys()))
    ap.add_argument("--days", type=int, default=7)
    args = ap.parse_args()
    asyncio.run(run_async(args.doc_types.split(","), args.days))


if __name__ == "__main__":
    main()

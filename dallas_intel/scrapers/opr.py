"""
Dallas County Clerk Official Public Records scraper (Kofile / publicsearch.us).

Source: https://dallas.tx.publicsearch.us/
Status: ⚠️ SEMI — JS-rendered, rate-limited

This is the CRITICAL source for motivated-seller leads:
  - Lis Pendens (suit affecting title)
  - Substitute trustee notices (mortgage foreclosure)
  - Federal/State/IRS tax liens
  - Mechanic's liens
  - Hospital liens
  - HOA liens
  - Affidavits of heirship
  - Quitclaim deeds
  - Abstracts of judgment

Kofile's publicsearch.us renders results client-side (React) so plain
requests won't work. We use Playwright with Chromium.

GOTCHAS:
  - Rate limiting: ~2-3 second delay between searches; too fast and you get
    a 30-minute IP cooldown.
  - Captcha: appears intermittently. The script will pause and ask you to
    solve it manually if detected.
  - Date filter: search runs against a max 90-day window per query — break
    larger ranges into chunks.

USAGE:
    python -m dallas_intel.scrapers.opr --doc-types LIS_PENDENS,SUBSTITUTE_TRUSTEE --days 7
"""
import argparse
import asyncio
import re
from datetime import datetime, timedelta

from dallas_intel.config import OPR_PUBLICSEARCH
from dallas_intel.db.init import get_connection
from dallas_intel.scrapers._utils import normalize_name


# Document type codes that map to motivated-seller signals.
# NOTE: Kofile internally uses different codes; the search UI exposes
# friendly names. The mapping below works against the search UI labels.
DOC_TYPE_LABELS = {
    "LIS_PENDENS": ["Lis Pendens", "LIS PENDENS"],
    "SUBSTITUTE_TRUSTEE": ["Substitute Trustee", "Trustee Notice", "Notice of Trustee Sale"],
    "TAX_LIEN": ["Federal Tax Lien", "State Tax Lien", "Tax Lien"],
    "MECHANICS_LIEN": ["Mechanic's Lien", "Mechanics Lien", "Affidavit of Lien"],
    "HOSPITAL_LIEN": ["Hospital Lien"],
    "HOA_LIEN": ["HOA Lien", "Homeowners Association Lien"],
    "AFFIDAVIT_HEIRSHIP": ["Affidavit of Heirship"],
    "QUITCLAIM": ["Quitclaim Deed"],
    "ABSTRACT_JUDGMENT": ["Abstract of Judgment"],
}


async def run_async(doc_types, days):
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
        browser = await p.chromium.launch(headless=False)  # headless=False during dev
        context = await browser.new_context(viewport={"width": 1400, "height": 900})
        page = await context.new_page()

        await page.goto(OPR_PUBLICSEARCH, timeout=60_000)
        await page.wait_for_load_state("networkidle")

        # Detect & wait through the "browser is out of date" warning if present
        try:
            await page.click("text=Continue", timeout=3000)
        except Exception:
            pass

        for code in doc_types:
            for label in DOC_TYPE_LABELS.get(code, []):
                print(f"[opr] searching '{label}' from {start:%Y-%m-%d} to {end:%Y-%m-%d}")
                try:
                    # The Kofile search UI selectors change occasionally. The flow is:
                    #   1. Open advanced search
                    #   2. Enter doc type label
                    #   3. Enter date range
                    #   4. Click search
                    # Inspect the live page if these break.
                    await page.click("button:has-text('Advanced')", timeout=5000)
                    await page.fill("input[placeholder*='Document Type']", label)
                    await page.click(f"text={label}")
                    await page.fill("input[name='dateFrom']", start.strftime("%m/%d/%Y"))
                    await page.fill("input[name='dateTo']", end.strftime("%m/%d/%Y"))
                    await page.click("button:has-text('Search')")
                    await page.wait_for_load_state("networkidle")

                    # Loop through result pages
                    while True:
                        rows = await page.query_selector_all("[data-testid='result-row']")
                        for row in rows:
                            text = (await row.inner_text()).strip()
                            doc_num = re.search(r"\b\d{10,15}\b", text)
                            date = re.search(r"\d{2}/\d{2}/\d{4}", text)
                            if not doc_num:
                                continue
                            grantor = await extract_field(row, "[data-testid='grantor']")
                            legal = await extract_field(row, "[data-testid='legal']")
                            conn.execute("""
                                INSERT OR REPLACE INTO recordings
                                    (doc_number, doc_type, filed_date, grantor, grantor_norm,
                                     legal_desc, source_url, last_seen)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                doc_num.group(0),
                                label.upper(),
                                date.group(0) if date else None,
                                grantor,
                                normalize_name(grantor or ""),
                                legal,
                                OPR_PUBLICSEARCH,
                                datetime.utcnow().isoformat(),
                            ))
                            inserted += 1

                        # Try to click "Next"; break if it doesn't exist or is disabled
                        next_btn = await page.query_selector("button[aria-label='Next page']")
                        if not next_btn:
                            break
                        disabled = await next_btn.get_attribute("disabled")
                        if disabled is not None:
                            break
                        await next_btn.click()
                        await page.wait_for_load_state("networkidle")
                        await asyncio.sleep(2.5)  # rate limit

                    conn.commit()
                except Exception as e:
                    print(f"[opr]   ERROR for '{label}': {e}")
                    # Likely a captcha or selector change. Pause for human.
                    print("[opr]   pausing 30s — solve captcha if visible, then resume")
                    await asyncio.sleep(30)

        await browser.close()

    conn.close()
    print(f"[opr] done. {inserted} recordings ingested.")


async def extract_field(row, selector):
    el = await row.query_selector(selector)
    if not el:
        return ""
    return (await el.inner_text()).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc-types", default=",".join(DOC_TYPE_LABELS.keys()))
    ap.add_argument("--days", type=int, default=7)
    args = ap.parse_args()
    asyncio.run(run_async(args.doc_types.split(","), args.days))


if __name__ == "__main__":
    main()

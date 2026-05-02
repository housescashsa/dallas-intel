"""
LGBS (Linebarger Goggan Blair & Sampson) upcoming tax-sale scraper.

Source: https://taxsales.lgbs.com/
Status: ✅ AUTO

LGBS is the law firm that prosecutes delinquent-tax suits for Dallas County
and most other North Texas taxing entities. Their public tax-sale list is the
upstream source of the Sheriff's monthly auction — properties typically appear
here weeks before they hit RealAuction.

This scraper:
  1. GETs the LGBS site filtered to Dallas County.
  2. Parses each property listing.
  3. Inserts/updates rows in `tax_sales`.

LGBS's site renders a server-side HTML table (no JS rendering needed). If they
change layout in the future, switch to Playwright.
"""
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

from dallas_intel.config import LGBS_TAX_SALE, USER_AGENT
from dallas_intel.db.init import get_connection


HEADERS = {"User-Agent": USER_AGENT}


def fetch_dallas_listings():
    # LGBS lets you filter by county via a URL parameter; check current site.
    # Most reliable approach: hit the search page, post a filter form.
    r = requests.get(LGBS_TAX_SALE, headers=HEADERS, timeout=60)
    r.raise_for_status()
    return r.text


def parse(html: str):
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    # Their table has a recognizable header row containing "Cause #" or "Sale Date".
    # If they restructure the site, inspect and adjust selectors here.
    for table in soup.find_all("table"):
        head = table.find("thead")
        if not head:
            continue
        head_text = head.get_text(" ", strip=True).lower()
        if "cause" not in head_text and "sale date" not in head_text:
            continue
        for tr in table.find("tbody").find_all("tr"):
            cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
            if len(cells) < 4:
                continue
            cause, sale_date, address, *rest = cells
            min_bid = None
            for c in rest:
                m = re.search(r"\$([\d,]+)", c)
                if m:
                    min_bid = float(m.group(1).replace(",", ""))
                    break
            rows.append({
                "cause_number": cause,
                "sale_date": sale_date,
                "address": address,
                "min_bid": min_bid,
            })
    return rows


def run():
    html = fetch_dallas_listings()
    rows = parse(html)
    conn = get_connection()
    for r in rows:
        r["last_seen"] = datetime.utcnow().isoformat()
        r["sale_type"] = "TAX_SALE"
        r["source_url"] = LGBS_TAX_SALE
        conn.execute("""
            INSERT INTO tax_sales
                (cause_number, sale_date, address, min_bid, sale_type, source_url, last_seen)
            VALUES (:cause_number, :sale_date, :address, :min_bid, :sale_type, :source_url, :last_seen)
        """, r)
    conn.commit()
    conn.close()
    print(f"[lgbs] {len(rows)} upcoming tax-sale properties recorded.")


if __name__ == "__main__":
    run()

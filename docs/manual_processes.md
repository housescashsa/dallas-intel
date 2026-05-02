# Manual Processes — Read This Before You Spend Money

These 8 sources can't be fully automated. Some are technically possible to scrape, but the legal, financial, or technical friction makes manual the right answer for a solo investor. Each section explains what the source is, why we stopped automating, and exactly what to do.

---

## 1. RealAuction Sheriff Sale (dallas.texas.sheriffsaleauctions.com)

**What it is:** The Dallas County Sheriff's office holds a tax-foreclosure auction on the **first Tuesday of every month**. Properties are sold to the highest bidder on the courthouse steps (now mirrored online via RealAuction). Winning bids are usually 50–70% of market value, sometimes lower.

**Why it's manual:**
- RealAuction requires identity verification (driver's license + SSN) before you can register.
- You must wire a **$1,000 refundable deposit** to participate as a bidder.
- Texas requires a **Written Statement of No Delinquent Taxes** (Form 50-307) on file with the county before you can bid — meaning you have to prove you don't owe Dallas County any property tax yourself.
- Bidding is real-time live auction style. You can't proxy this through a script.

**What to do:**
1. Go to https://dallas.texas.sheriffsaleauctions.com/ and click **Register**.
2. Download Form 50-307 (Written Statement). Fill it out, sign it, and file it with the **Dallas County Tax Assessor's office**, 500 Elm St, Dallas, TX 75202. They'll stamp it.
3. Mail or upload the stamped form to RealAuction.
4. Wire your $1,000 deposit (instructions on their site).
5. Auctions are the **first Tuesday at 10am Central**. Properties drop on the site about **3 weeks before** each auction.
6. The **upcoming list** (which IS automated by `lgbs_tax_sale.py` in this repo) gives you 2–3 weeks of warning to drive properties before bidding.

**Strategy tip for new investors:** Don't bid the first 2–3 auctions. Watch what wins, what doesn't, and at what prices. Most properties at sheriff sale go to a small group of regulars who know the comps cold.

---

## 2. PACER (Federal Bankruptcy Filings)

**What it is:** When someone files Chapter 7 or 13 bankruptcy, all their property gets listed in court documents — and they're often eager to short-sale or deed-in-lieu before the trustee takes over. Bankruptcies are public record, but only accessible through PACER.

**Why it's manual:**
- PACER charges **$0.10 per page**, capped at $3 per document.
- The Northern District of Texas Bankruptcy Court doesn't expose a free bulk feed.
- Automation would mean racking up real-money charges on every search.
- Filings are scanned PDFs — full text search costs more.

**What to do:**
1. Register at https://pacer.uscourts.gov/ (it's free to register, you only pay when you pull docs).
2. Use **PACER Case Locator** to search Northern District of Texas, Bankruptcy.
3. Filter by date filed (last 30 days) and chapter (7 and 13).
4. Look for **Schedule A/B** in each case — it lists all real estate owned by the filer.
5. If a Dallas County address appears, cross-reference with your DCAD spine to enrich.

**Cost reality:** Pulling 50 cases per month with Schedule A/B downloads runs ~$30–50. The fee is waived if your quarterly bill is under $30.

**Free alternative:** Use **Justia** (https://dockets.justia.com/) for case headers and party names. You won't get Schedule A details, but you can identify recent filers and then pay PACER only for their schedules.

---

## 3. Daily Commercial Record (Newspaper of Record)

**What it is:** A subscription legal newspaper that publishes **every single foreclosure notice in Dallas County** before it hits the courthouse steps. Texas requires non-judicial foreclosures to be posted publicly for **21 days** before the auction — DCR is where they appear first.

**Why it's manual:**
- DCR is a **paid subscription** (~$200/year).
- They explicitly forbid scraping in their TOS.
- The PDF e-edition is delivered behind login.
- Even if you scraped it, DCR would notice and revoke you.

**What to do:**
1. Subscribe at https://www.dailycommercialrecord.com/ (~$200/yr, sometimes discounted).
2. Each weekday morning the new issue lands in your email as a PDF.
3. Search the PDF for **"Notice of Substitute Trustee Sale"** — that's the foreclosure section.
4. Each notice lists: trustee, lender, original borrower, property legal description, date of sale, time, and minimum bid.
5. Run each address through your dashboard to enrich with DCAD data and score.

**Shortcut:** The OPR scraper (`opr.py`) already pulls Substitute Trustee notices when they're recorded with the County Clerk — DCR is faster (often 2–3 days earlier) and more complete, but the OPR scrape catches ~80% for free.

**Strategy tip:** The DCR subscription is the single best data investment for a serious foreclosure investor in Dallas. The 21-day window is the entire game.

---

## 4. Foreclosure Postings (In-Person)

**What it is:** Texas law requires foreclosure notices to be **physically posted on the courthouse door** in addition to publication. Some lenders and trustees post **only in person**, never digitally — these are the "hidden" foreclosures that the ScraperBros don't see.

**Why it's manual:**
- Some notices are taped to a corkboard inside the courthouse and never digitized.
- You literally have to walk in and read them.
- This represents maybe 5–10% of foreclosures, but they're often the least-competitive deals.

**What to do:**
1. Go to **George L. Allen Sr. Courts Building, 600 Commerce St, Dallas, TX 75202**.
2. Lobby has a wall of posted notices, refreshed daily.
3. Photograph each one with your phone.
4. Run addresses through DCAD/your dashboard.
5. Best done **the Friday before the first Tuesday** of each month (the foreclosure date).

**Frequency:** Once a month is enough. Some investors hire a runner ($25–50/visit) to do this.

---

## 5. LGBS Tax Sale Bidder Registration

**What it is:** Linebarger Goggan Blair & Sampson is the law firm that prosecutes property tax suits for Dallas County. To bid at a **resale** (struck-off properties from previous sheriff sales), you must register with LGBS separately from RealAuction.

**Why it's manual:**
- Same Form 50-307 ("Written Statement") requirement as sheriff sale.
- LGBS reviews each registration manually (1–2 business day delay).
- They only accept the registration in person, by mail, or by fax (no online portal).

**What to do:**
1. Get Form 50-307 stamped by Dallas County Tax Assessor (same as Step 2 in #1 above — you can use the same stamped form for both).
2. Mail to: **Linebarger Goggan Blair & Sampson, LLP, 2777 N Stemmons Fwy Ste 1000, Dallas, TX 75207**.
3. Wait for confirmation email.
4. Show up to the resale on the assigned date with cashier's check for full bid amount.

**Why bother:** Resale properties are the ones nobody bid on at the original sheriff sale. They get re-listed at **the original tax debt amount** (often well under market). You can find genuine $40k–$80k deals here on properties worth $200k+.

---

## 6. Skip Tracing (the part that makes this whole system worth it)

**What it is:** Public records have the owner's **name and mailing address**. To actually reach them, you need their **phone number and email**. That's skip tracing — matching a name+address to contact info.

**Why it's manual (well, paid):**
- Phone numbers and emails aren't public record. They live in private databases (LexisNexis, TLO, etc.) that require licensed access.
- A scraper can't legally pull this data — and even if it could, the data would be 5+ years stale.
- You **must** use a paid vendor.

**What to do — vendor options:**

| Vendor | Cost | Best for |
|--------|------|----------|
| **BatchSkipTracing** | $0.10–0.15/record bulk | Cheap, decent quality, integrates with REI Reply and GHL |
| **REISkip** | $0.07/record bulk | Cheapest reliable; some data is older |
| **PropStream** | $99/mo (skip included) | If you also want comps + heat maps |
| **Skip Genie** | Manual one-off | When you need cellphones for top 5–10 leads |
| **Spokeo / TruePeopleSearch** | Free | Very poor quality; only use as a last resort |

**My recommendation for a new investor:** Start with BatchSkipTracing. Upload the `dallas-skiptrace-YYYY-MM-DD.csv` from the **Skip Trace CSV** button on your dashboard. They process in 5–10 minutes and return a CSV with phone + email columns appended. Re-import that into GHL.

**Cost math:** 500 hot leads × $0.12 = $60. If 3% convert to a contract and 1 in 5 contracts becomes a deal averaging $15k assignment, that's $9k revenue on $60 spent.

---

## 7. Scanned Foreclosure PDFs (OCR Edge Cases)

**What it is:** Some county recordings — especially older liens and foreclosure notices — are scanned PDFs, not native digital documents. OCR works on most, but ~15% are too low-quality (faxed, handwritten endorsements, stamps over text).

**Why it's manual (sometimes):**
- The OPR scraper pulls the PDF and runs OCR via Tesseract.
- When OCR confidence is low, the script flags the doc and skips it.
- Roughly 1 in 7 docs needs human review.

**What to do:**
1. The dashboard will show flagged-for-review records with no Owner / Grantor populated.
2. Click the doc link to open the original PDF.
3. Read the relevant fields (Grantor, Legal Description, Amount).
4. Enter manually via the **Import Tax List** modal or directly into the database.

**Future improvement:** Switch from Tesseract to a paid vision API (Google Document AI, AWS Textract). Cost is ~$0.05/doc but accuracy hits 99%+.

---

## 8. Suburb Code Violation Portals

**What it is:** Dallas Open Data covers the **City of Dallas** only (~60% of the county). The other ~40% — Garland, Mesquite, Irving, Richardson, Carrollton, Grand Prairie, DeSoto, Lancaster, Cedar Hill, Duncanville, Farmers Branch, Coppell — each run their own code enforcement portal.

**Why it's manual:**
- Each city uses a different vendor (Tyler MyCivic, Accela, SeeClickFix, custom).
- Portals don't expose APIs.
- Login requirements vary; some require resident verification.
- 12 portals × maintenance overhead is more work than the leads are worth for most investors.

**What to do:**

| City | Portal | Approach |
|------|--------|----------|
| Garland | https://www.garlandtx.gov/ → Code Compliance | Manual search by address; phone tip line works too |
| Mesquite | Mesquite Connect | Free login, search by address |
| Irving | Irving 311 / IrvingConnect | Browser-only |
| Richardson | RichardsonNow app | Best as mobile-only |
| All others | Call the city's code enforcement line | Tell them you're researching a specific address |

**Practical approach for a new investor:** Don't try to monitor all 12. Pick the 2–3 suburbs you're actively buying in and check their portals weekly. The Dallas Open Data 311 feed (which IS automated) plus DCAD addressing usually gives you 70%+ of total Dallas County code-violation leads.

---

## Quick Reference — When to Pay vs When to DIY

| Situation | Pay | DIY |
|-----------|-----|-----|
| You have <$500/mo budget | DIY everything | — |
| You have $500–2000/mo | DCR + BatchSkipTracing | Everything else |
| You have $2000+/mo | DCR + PropStream + REISkip + a runner for in-person postings | — |
| You're brand new and uncertain | Run the auto-scrapers for 30 days first | Don't pay anything until you see leads converting |

---

## When in doubt

The motto: **Automate what's free, pay for what compounds.** The free automated sources in this repo (DCAD, TRW, 311, LGBS, OPR, Courts Portal) will give you 80% of the lead volume. The paid manual stuff (DCR, PACER, skip-trace) is what differentiates investors who close 1 deal/month from investors who close 5+.

"""Central config — all source URLs, constants, paths."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "dallas_intel.sqlite"

DATA_DIR.mkdir(exist_ok=True)
RAW_DIR.mkdir(exist_ok=True)

# ---- Source URLs ----
DCAD_DATA_PRODUCTS = "https://www.dallascad.org/dataproducts.aspx"
DCAD_GIS_PRODUCTS = "https://www.dallascad.org/gisdataproducts.aspx"
DCAD_SEARCH = "https://www.dallascad.org/SearchAddr.aspx"

TAX_ROLL_TRW_PAGE = "https://www.dallascounty.org/departments/tax/tax-roll.php"
TAX_LOOKUP_BASE = "https://www.dallasact.com/act_webdev/dallas/searchbyproperty.jsp"

DALLAS_OPEN_DATA = "https://www.dallasopendata.com"
SODA_311_DATASET = "gc4d-8a49"  # 311 service requests (current FY)
# To find the current dataset id, browse https://www.dallasopendata.com/browse?tags=311

OPR_PUBLICSEARCH = "https://dallas.tx.publicsearch.us/"
COUNTY_CLERK_FORECLOSURES = (
    "https://www.dallascounty.org/government/county-clerk/recording/foreclosures.php"
)
COURTS_PORTAL = "https://www.dallascounty.org/services/record-search/"

LGBS_TAX_SALE = "https://taxsales.lgbs.com/"
SHERIFF_REALAUCTION = "https://dallas.texas.sheriffsaleauctions.com/"

TX_SOS_ENTITY = "https://www.sos.state.tx.us/corp/sosda/index.shtml"
TX_COMPTROLLER_FRANCHISE = "https://comptroller.texas.gov/taxes/franchise/"

HUD_USPS_VACANCY = "https://www.huduser.gov/portal/datasets/usps.html"

# ---- Lead types ----
LEAD_TYPES = [
    "FORECLOSURE", "LIS PENDENS", "TAX", "PROBATE",
    "CODE", "LIEN", "JUDGMENT", "QUITCLAIM",
    "EVICTION", "DIVORCE",
]

USER_AGENT = (
    "Mozilla/5.0 (compatible; DallasIntel/1.0; +https://github.com/yourusername/dallas_intel)"
)

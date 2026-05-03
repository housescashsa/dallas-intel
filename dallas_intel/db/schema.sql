-- Dallas Property Intel SQLite schema.
-- Spine: parcels (from DCAD). Everything else joins on dcad_account or address.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ===== Parcels (from DCAD bulk download) =====
CREATE TABLE IF NOT EXISTS parcels (
    dcad_account     TEXT PRIMARY KEY,
    owner_name       TEXT,
    owner_name_norm  TEXT,            -- normalized for fuzzy matching
    mailing_address  TEXT,
    property_address TEXT,
    city             TEXT,
    zip              TEXT,
    legal_desc       TEXT,
    year_built       INTEGER,
    sqft             INTEGER,
    beds             INTEGER,
    baths            REAL,
    lot_size         INTEGER,
    last_sale_date   TEXT,
    last_sale_price  INTEGER,
    market_value     INTEGER,
    is_homestead     INTEGER DEFAULT 0,
    out_of_state_mailing INTEGER DEFAULT 0,
    is_llc_owner     INTEGER DEFAULT 0,
    last_updated     TEXT
);
CREATE INDEX IF NOT EXISTS idx_parcels_owner_norm ON parcels(owner_name_norm);
CREATE INDEX IF NOT EXISTS idx_parcels_address ON parcels(property_address);

-- ===== Tax delinquency =====
CREATE TABLE IF NOT EXISTS tax_delinquencies (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    dcad_account    TEXT NOT NULL,
    tax_year        INTEGER,
    amount_due      REAL,
    years_delinquent INTEGER,
    last_seen       TEXT
);
CREATE INDEX IF NOT EXISTS idx_tax_account ON tax_delinquencies(dcad_account);

-- ===== Recordings (deeds, lis pendens, liens, foreclosures) =====
CREATE TABLE IF NOT EXISTS recordings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_number      TEXT UNIQUE,
    doc_type        TEXT,             -- LIS PENDENS, ABSTRACT OF JUDGMENT, etc.
    filed_date      TEXT,
    grantor         TEXT,
    grantor_norm    TEXT,
    grantee         TEXT,
    legal_desc      TEXT,
    amount          REAL,
    dcad_account    TEXT,             -- joined post-import via fuzzy match
    source_url      TEXT,
    raw_blob        TEXT,
    last_seen       TEXT
);
CREATE INDEX IF NOT EXISTS idx_rec_grantor_norm ON recordings(grantor_norm);
CREATE INDEX IF NOT EXISTS idx_rec_doc_type ON recordings(doc_type);
CREATE INDEX IF NOT EXISTS idx_rec_account ON recordings(dcad_account);

-- ===== Court filings (probate, divorce, eviction, civil) =====
CREATE TABLE IF NOT EXISTS court_filings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    case_number     TEXT UNIQUE,
    case_type       TEXT,             -- PROBATE, DIVORCE, EVICTION, CIVIL
    filed_date      TEXT,
    party_name      TEXT,
    party_name_norm TEXT,
    court           TEXT,
    status          TEXT,
    source_url      TEXT,
    last_seen       TEXT
);
CREATE INDEX IF NOT EXISTS idx_court_party ON court_filings(party_name_norm);
CREATE INDEX IF NOT EXISTS idx_court_type ON court_filings(case_type);

-- ===== Code violations & 311 =====
CREATE TABLE IF NOT EXISTS code_violations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sr_number       TEXT UNIQUE,
    address         TEXT,
    violation_type  TEXT,
    status          TEXT,
    open_date       TEXT,
    close_date      TEXT,
    council_district TEXT,
    dcad_account    TEXT,
    last_seen       TEXT
);
CREATE INDEX IF NOT EXISTS idx_code_address ON code_violations(address);
CREATE INDEX IF NOT EXISTS idx_code_account ON code_violations(dcad_account);

-- ===== Tax sale upcoming (LGBS + sheriff) =====
CREATE TABLE IF NOT EXISTS tax_sales (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    cause_number    TEXT,
    sale_date       TEXT,
    address         TEXT,
    legal_desc      TEXT,
    min_bid         REAL,
    dcad_account    TEXT,
    sale_type       TEXT,             -- TAX_SALE, STRUCK_OFF, RESALE
    source_url      TEXT,
    last_seen       TEXT
);

-- ===== The unified leads view (the "spine" the dashboard reads from) =====
CREATE TABLE IF NOT EXISTS leads (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    dcad_account    TEXT,
    lead_type       TEXT,             -- one of LEAD_TYPES
    score           INTEGER,
    flags           TEXT,             -- JSON array
    doc_number      TEXT,
    filed_date      TEXT,
    owner_name      TEXT,
    property_address TEXT,
    city            TEXT,
    zip             TEXT,
    mailing_address TEXT,
    amount          REAL,
    legal_desc      TEXT,
    source_url      TEXT,
    last_scored     TEXT,
    UNIQUE(dcad_account, lead_type, doc_number)
);
CREATE INDEX IF NOT EXISTS idx_leads_score ON leads(score);
CREATE INDEX IF NOT EXISTS idx_leads_type ON leads(lead_type);
CREATE INDEX IF NOT EXISTS idx_leads_city ON leads(city);

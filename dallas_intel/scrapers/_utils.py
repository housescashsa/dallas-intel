"""Shared utilities used across scrapers."""
import re


_LLC_PATTERNS = re.compile(
    r"\b(LLC|L\.L\.C|INC|LP|LLP|LTD|CORP|CORPORATION|HOLDINGS|TRUST|ESTATE OF)\b",
    re.IGNORECASE,
)
_PUNCT = re.compile(r"[^\w\s]")
_WS = re.compile(r"\s+")
_SUFFIXES = re.compile(r"\b(JR|SR|II|III|IV|V|MD|PHD|ESQ)\b\.?", re.IGNORECASE)


def normalize_name(name: str) -> str:
    """Lowercased, punctuation-stripped, suffix-removed for fuzzy matching."""
    if not name:
        return ""
    s = name.upper()
    s = _SUFFIXES.sub("", s)
    s = _PUNCT.sub(" ", s)
    s = _WS.sub(" ", s).strip()
    return s


def is_llc_owner(name: str) -> bool:
    return bool(_LLC_PATTERNS.search(name or ""))


def is_estate(name: str) -> bool:
    return "ESTATE OF" in (name or "").upper()


# Texas state codes that count as in-state (the rest = out of state mailing)
_TX_STATE_CODES = {"TX", "TEXAS"}


def is_out_of_state(mailing_address: str) -> bool:
    if not mailing_address:
        return False
    upper = mailing_address.upper()
    # Look for any 2-letter state code that isn't TX
    m = re.search(r"\b([A-Z]{2})\s+\d{5}", upper)
    if m and m.group(1) not in _TX_STATE_CODES:
        return True
    return False


def address_key(address: str) -> str:
    """Normalize an address for fuzzy matching across sources."""
    if not address:
        return ""
    s = address.upper()
    s = re.sub(r"\b(STREET|ST|AVENUE|AVE|BOULEVARD|BLVD|DRIVE|DR|ROAD|RD|LANE|LN|COURT|CT|CIRCLE|CIR|PARKWAY|PKWY|PLACE|PL)\b\.?", "", s)
    s = re.sub(r"\b(NORTH|SOUTH|EAST|WEST|N|S|E|W)\b\.?", "", s)
    s = _PUNCT.sub("", s)
    s = _WS.sub(" ", s).strip()
    return s

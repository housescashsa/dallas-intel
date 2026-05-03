"""
FastAPI backend that serves leads from the SQLite database to the dashboard.
Run with: uvicorn dallas_intel.api:app --reload --port 8000
"""
import json
import sqlite3
from pathlib import Path
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from dallas_intel.config import DB_PATH

app = FastAPI(title="Dallas Property Intel API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


@app.get("/api/health")
def health():
    return {"ok": True, "db": str(DB_PATH), "exists": Path(DB_PATH).exists()}


@app.get("/api/stats")
def stats():
    c = conn()
    row = c.execute("""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN score >= 70 THEN 1 ELSE 0 END) AS hot,
            SUM(CASE WHEN score >= 50 AND score < 70 THEN 1 ELSE 0 END) AS warm,
            SUM(CASE WHEN score >= 30 AND score < 50 THEN 1 ELSE 0 END) AS active,
            SUM(CASE WHEN property_address != "" AND property_address NOT LIKE "0 %" THEN 1 ELSE 0 END) AS with_address
        FROM leads
    """).fetchone()
    last = c.execute("SELECT MAX(last_scored) AS t FROM leads").fetchone()
    c.close()
    return {**dict(row), "last_updated": last["t"]}


@app.get("/api/leads")
def list_leads(
    score_min: int = 0,
    lead_type: str | None = None,
    city: str | None = None,
    search: str | None = None,
    filed_from: str | None = None,
    filed_to: str | None = None,
    years_delinquent_min: int | None = None,
    limit: int = Query(default=500, le=10000),
):
    c = conn()
    sql = """
        SELECT l.id, l.dcad_account, l.lead_type, l.score, l.flags,
               l.doc_number, l.filed_date, l.owner_name, l.property_address,
               l.city, l.zip, l.mailing_address, l.amount, l.legal_desc,
               p.market_value, p.year_built, p.sqft, p.beds, p.baths,
               t.years_delinquent
        FROM leads l
        LEFT JOIN parcels p ON p.dcad_account = l.dcad_account
        LEFT JOIN tax_delinquencies t ON t.dcad_account = l.dcad_account
        WHERE l.score >= ?
          AND (l.property_address NOT LIKE "0 %" OR l.property_address IS NULL)
    """
    args = [score_min]
    if lead_type:
        sql += " AND l.lead_type = ?"
        args.append(lead_type)
    if city:
        sql += " AND l.city LIKE ?"
        args.append("%" + city + "%")
    if search:
        sql += " AND (l.owner_name LIKE ? OR l.property_address LIKE ?)"
        args.extend(["%" + search + "%", "%" + search + "%"])
    if filed_from:
        sql += " AND l.filed_date >= ?"
        args.append(filed_from)
    if filed_to:
        sql += " AND l.filed_date <= ?"
        args.append(filed_to)
    if years_delinquent_min is not None:
        sql += " AND t.years_delinquent >= ?"
        args.append(years_delinquent_min)
    sql += " ORDER BY l.score DESC, l.amount DESC LIMIT ?"
    args.append(limit)

    rows = []
    for row in c.execute(sql, args):
        d = dict(row)
        try:
            d["flags"] = json.loads(d["flags"]) if d["flags"] else []
        except Exception:
            d["flags"] = []
        rows.append(d)
    c.close()
    return {"count": len(rows), "leads": rows}


@app.get("/api/lead-types")
def lead_types():
    c = conn()
    rows = c.execute("""
        SELECT lead_type, COUNT(*) AS n
        FROM leads
        GROUP BY lead_type
        ORDER BY n DESC
    """).fetchall()
    c.close()
    return {"types": [dict(r) for r in rows]}


@app.get("/api/cities")
def cities():
    c = conn()
    rows = c.execute("""
        SELECT city, COUNT(*) AS n
        FROM leads
        WHERE city != ""
        GROUP BY city
        ORDER BY n DESC
        LIMIT 20
    """).fetchall()
    c.close()
    return {"cities": [dict(r) for r in rows]}

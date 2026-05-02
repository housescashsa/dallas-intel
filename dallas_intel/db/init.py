"""Initialize the SQLite database from schema.sql."""
import sqlite3
from pathlib import Path
from dallas_intel.config import DB_PATH


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    schema = (Path(__file__).parent / "schema.sql").read_text()
    conn = get_connection()
    conn.executescript(schema)
    conn.commit()
    conn.close()
    print(f"[db] initialized at {DB_PATH}")


if __name__ == "__main__":
    init_db()

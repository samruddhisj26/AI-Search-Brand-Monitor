"""
brand-monitor/db.py — SQLite database layer
"""

import sqlite3
import json
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "brand_monitor.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS brands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            keywords TEXT NOT NULL,
            email TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS query_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand_id INTEGER NOT NULL DEFAULT 0,
            brand_name TEXT NOT NULL DEFAULT '',
            platform TEXT NOT NULL,
            keyword TEXT NOT NULL,
            prompt TEXT NOT NULL,
            raw_response TEXT,
            error TEXT,
            queried_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query_log_id INTEGER NOT NULL UNIQUE,
            brand_mentioned INTEGER NOT NULL DEFAULT 0,
            sentiment TEXT,
            accuracy TEXT,
            competitors TEXT,
            visibility_score INTEGER DEFAULT 0,
            summary TEXT,
            analyzed_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (query_log_id) REFERENCES query_log(id)
        );

        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand_id INTEGER NOT NULL,
            week_start TEXT NOT NULL,
            week_end TEXT NOT NULL,
            summary TEXT,
            delivered_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (brand_id) REFERENCES brands(id)
        );

        CREATE INDEX IF NOT EXISTS idx_query_log_brand ON query_log(brand_id, queried_at);
        CREATE INDEX IF NOT EXISTS idx_analysis_query ON analysis(query_log_id);
        CREATE INDEX IF NOT EXISTS idx_reports_brand ON reports(brand_id, week_start);
    """)
    conn.commit()
    conn.close()

# ── Brand CRUD ──

def add_brand(name, keywords, email=None):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO brands (name, keywords, email) VALUES (?, ?, ?)",
            (name, json.dumps(keywords), email)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_brands():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM brands").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_brand(brand_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM brands WHERE id = ?", (brand_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

# ── Query Log ──

def log_query(brand_id, brand_name, platform, keyword, prompt, raw_response=None, error=None):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO query_log (brand_id, brand_name, platform, keyword, prompt, raw_response, error) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (brand_id, brand_name, platform, keyword, prompt, raw_response, error)
    )
    conn.commit()
    query_id = cur.lastrowid
    conn.close()
    return query_id

def get_queries(brand_id, since=None, platform=None):
    conn = get_conn()
    parts = ["SELECT * FROM query_log WHERE brand_id = ?"]
    params = [brand_id]
    if since:
        parts.append("AND queried_at >= ?")
        params.append(since)
    if platform:
        parts.append("AND platform = ?")
        params.append(platform)
    parts.append("ORDER BY queried_at DESC")
    rows = conn.execute(" ".join(parts), params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── Analysis ──

def save_analysis(query_log_id, brand_mentioned, sentiment, accuracy, competitors, visibility_score, summary):
    conn = get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO analysis
           (query_log_id, brand_mentioned, sentiment, accuracy, competitors, visibility_score, summary)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (query_log_id, 1 if brand_mentioned else 0, sentiment, accuracy,
         json.dumps(competitors), visibility_score, summary)
    )
    conn.commit()
    conn.close()

def get_latest_analysis(brand_id, platform=None, keyword=None):
    conn = get_conn()
    parts = [
        "SELECT a.*, q.platform, q.keyword, q.queried_at"
        " FROM analysis a JOIN query_log q ON a.query_log_id = q.id"
        " WHERE q.brand_id = ?"
    ]
    params = [brand_id]
    if platform:
        parts.append("AND q.platform = ?")
        params.append(platform)
    if keyword:
        parts.append("AND q.keyword = ?")
        params.append(keyword)
    parts.append("ORDER BY q.queried_at DESC LIMIT 1")
    row = conn.execute(" ".join(parts), params).fetchone()
    conn.close()
    return dict(row) if row else None

def get_previous_analysis(brand_id, platform, keyword, before):
    """Get the analysis before a given datetime for comparison."""
    conn = get_conn()
    row = conn.execute(
        """SELECT a.*, q.platform, q.keyword, q.queried_at
           FROM analysis a JOIN query_log q ON a.query_log_id = q.id
           WHERE q.brand_id = ? AND q.platform = ? AND q.keyword = ? AND q.queried_at < ?
           ORDER BY q.queried_at DESC LIMIT 1""",
        (brand_id, platform, keyword, before)
    ).fetchone()
    conn.close()
    return dict(row) if row else None

# ── Reports ──

def save_report(brand_id, week_start, week_end, summary):
    conn = get_conn()
    conn.execute(
        "INSERT INTO reports (brand_id, week_start, week_end, summary) VALUES (?, ?, ?, ?)",
        (brand_id, week_start, week_end, summary)
    )
    conn.commit()
    conn.close()

def get_reports(brand_id, limit=10):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM reports WHERE brand_id = ? ORDER BY week_start DESC LIMIT ?",
        (brand_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    init_db()
    print("Database initialized at", DB_PATH)
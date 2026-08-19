"""
tests/test_db.py — smoke tests for brand_monitor/db.py

Scope: schema creation + CRUD round-trips only. Not a coverage exercise —
we are not testing every filter combination of get_queries()/get_reports(),
just enough to prove the critical path (init, insert, read back) works.

Every test uses the `temp_db_path` fixture from conftest.py, which points
brand_monitor.config at a tmp_path-scoped SQLite file and clears the
override afterwards. Never touches the developer's real brand_monitor.db.
"""

import json
import sqlite3

from brand_monitor import db


def test_init_db_creates_all_tables_and_indices(temp_db_path):
    db.init_db()

    conn = sqlite3.connect(temp_db_path)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert {"brands", "query_log", "analysis", "reports"} <= tables

        indices = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        assert {
            "idx_query_log_brand",
            "idx_analysis_query",
            "idx_reports_brand",
        } <= indices
    finally:
        conn.close()


def test_add_brand_then_get_brands_and_get_brand_round_trip(temp_db_path):
    db.init_db()

    ok = db.add_brand("Figma", ["design tool", "prototyping"], email="a@example.com")
    assert ok is True

    brands = db.get_brands()
    assert len(brands) == 1
    assert brands[0]["name"] == "Figma"
    assert json.loads(brands[0]["keywords"]) == ["design tool", "prototyping"]
    assert brands[0]["email"] == "a@example.com"

    fetched = db.get_brand(brands[0]["id"])
    assert fetched is not None
    assert fetched["name"] == "Figma"


def test_get_brand_returns_none_for_missing_id(temp_db_path):
    db.init_db()
    assert db.get_brand(999) is None


def test_add_brand_duplicate_name_returns_false(temp_db_path):
    db.init_db()

    assert db.add_brand("Notion", ["productivity"]) is True
    assert db.add_brand("Notion", ["different keywords"]) is False

    # Only the first insert should have taken effect.
    brands = db.get_brands()
    assert len(brands) == 1


def test_log_query_returns_usable_row_id(temp_db_path):
    db.init_db()

    query_id = db.log_query(
        brand_id=1,
        brand_name="Figma",
        platform="chatgpt",
        keyword="best design tool",
        prompt="What is the best design tool?",
        raw_response="Figma is great.",
    )

    assert isinstance(query_id, int)
    assert query_id > 0

    rows = db.get_queries(brand_id=1)
    assert len(rows) == 1
    assert rows[0]["id"] == query_id
    assert rows[0]["raw_response"] == "Figma is great."


def test_save_analysis_then_get_latest_analysis_round_trip(temp_db_path):
    db.init_db()

    query_id = db.log_query(
        brand_id=1,
        brand_name="Figma",
        platform="chatgpt",
        keyword="best design tool",
        prompt="What is the best design tool?",
        raw_response="Figma is great.",
    )

    db.save_analysis(
        query_log_id=query_id,
        brand_mentioned=True,
        sentiment="positive",
        accuracy="accurate",
        competitors=["Sketch", "Adobe XD"],
        visibility_score=80,
        summary="Figma was featured prominently.",
    )

    latest = db.get_latest_analysis(brand_id=1)
    assert latest is not None
    assert latest["brand_mentioned"] == 1
    assert latest["sentiment"] == "positive"
    assert latest["visibility_score"] == 80
    # competitors round-trips through json.dumps/json.loads unchanged.
    assert json.loads(latest["competitors"]) == ["Sketch", "Adobe XD"]


def test_get_latest_analysis_returns_none_when_no_analysis_exists(temp_db_path):
    db.init_db()
    assert db.get_latest_analysis(brand_id=1) is None


def test_save_report_then_get_reports_round_trip(temp_db_path):
    db.init_db()

    db.add_brand("Figma", ["design tool"])
    brand = db.get_brands()[0]

    db.save_report(
        brand_id=brand["id"],
        week_start="2026-08-10",
        week_end="2026-08-16",
        summary="Visibility improved this week.",
    )

    reports = db.get_reports(brand["id"])
    assert len(reports) == 1
    assert reports[0]["week_start"] == "2026-08-10"
    assert reports[0]["summary"] == "Visibility improved this week."

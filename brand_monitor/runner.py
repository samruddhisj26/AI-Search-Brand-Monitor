#!/usr/bin/env python3
"""
brand_monitor/runner.py — Multi-brand orchestrator: query → analyze → dashboard

Not run directly. `process_brand()` and `run_multi_brand_cycle()` are called
by `brand-monitor scan` (see cli.py's `_cmd_scan()`), which handles both the
single-brand (`--brand NAME`) and all-brands flows.

Produces:
  1. Rich terminal dashboard (stdout)
  2. Dashboard saved to output/latest-dashboard.txt (ANSI-stripped fallback)
  3. Raw data in brand_monitor.db
"""

import json
import os
import time
from datetime import datetime, timedelta, timezone

from . import config
from .db import init_db, log_query, save_analysis, get_previous_analysis, save_report
from .query import run_queries
from .analyze import analyze_all
from .dashboard import render_full_dashboard
from .brands import BRANDS, get_brand_keywords, get_brand_category


def process_brand(brand_def):
    """Run query → analyze for a single brand. Returns list of analysis dicts."""
    name = brand_def["name"]
    category = brand_def["category"]
    keywords = brand_def["keywords"]

    print(f"\n  ── {name} ({category}) ──")

    # Run queries
    query_results = run_queries(name, keywords)

    # Log to DB, keeping each row's id so we can attach its analysis below
    query_log_ids = [
        log_query(
            brand_id=0,
            brand_name=name,
            platform=q["platform"],
            keyword=q["keyword"],
            prompt=q["prompt"],
            raw_response=q["response"],
            error=q["error"],
        )
        for q in query_results
    ]

    # Analyze
    analyses = analyze_all(name, query_results)
    print(f"  ✓ {len(analyses)} analyses complete")

    # Add platform/keyword to each analysis for the dashboard, and persist to DB
    for i, a in enumerate(analyses):
        if i < len(query_results):
            a["platform"] = query_results[i]["platform"]
            a["keyword"] = query_results[i]["keyword"]
        if i < len(query_log_ids):
            save_analysis(
                query_log_id=query_log_ids[i],
                brand_mentioned=a.get("brand_mentioned", False),
                sentiment=a.get("sentiment"),
                accuracy=a.get("accuracy"),
                competitors=a.get("competitors", []),
                visibility_score=a.get("visibility_score", 0),
                summary=a.get("summary", ""),
            )

    return analyses


def run_multi_brand_cycle():
    """Process all brands and render dashboard."""
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  🚀 AI Search Brand Monitor — Multi-Brand Scan")
    print(f"║  {datetime.now(timezone.utc).strftime('%B %d, %Y at %H:%M UTC')}")
    print(f"║  {len(BRANDS)} brands, {sum(len(b['keywords']) for b in BRANDS)} total keywords")
    print("╚══════════════════════════════════════════════════════════════╝")

    init_db()
    all_results = {}
    brand_info = {b["name"]: {"category": b["category"]} for b in BRANDS}

    total_queries = 0
    start_time = time.time()

    for i, brand in enumerate(BRANDS, 1):
        print(f"\n[{i}/{len(BRANDS)}] ", end="")
        try:
            analyses = process_brand(brand)
            all_results[brand["name"]] = analyses
            total_queries += len(analyses)
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            all_results[brand["name"]] = []

    elapsed = time.time() - start_time
    mins = int(elapsed // 60)
    secs = int(elapsed % 60)

    print(f"\n{'='*60}")
    print(f"  ✅ All brands processed in {mins}m {secs}s")
    print(f"  {total_queries} total queries across {len(BRANDS)} brands")
    print(f"{'='*60}\n")

    # ── Render dashboard ──
    render_full_dashboard(all_results, brand_info)

    # ── Save output ──
    output_dir = config.get_output_dir()
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "latest-dashboard.txt")

    # Capture rich output to file (strip ANSI for compatibility)
    try:
        from rich.text import Text
        from io import StringIO
        from rich.console import Console as RichConsole

        string_io = StringIO()
        file_console = RichConsole(file=string_io, force_terminal=False)
        file_console.print(f"AI Search Brand Monitor — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
        file_console.print(f"Brands scanned: {len(BRANDS)}")
        for brand_name, analyses in all_results.items():
            mentioned = sum(1 for a in analyses if a.get("brand_mentioned"))
            avg_score = sum(a.get("visibility_score", 0) for a in analyses) / max(len(analyses), 1)
            file_console.print(f"  {brand_name:20s} → {mentioned}/{len(analyses)} queries, score: {avg_score:.0f}/100")
        with open(output_path, "w") as f:
            f.write(string_io.getvalue())
        print(f"\n[Dashboard summary saved to {output_path}]")
    except Exception as e:
        print(f"\n[Could not save dashboard: {e}]")

    return all_results
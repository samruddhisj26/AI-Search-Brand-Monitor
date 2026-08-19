#!/usr/bin/env python3
"""
Reprocess existing query_log entries through the analysis pipeline,
skipping the query phase. Reads 90 existing responses from DB,
analyzes each one, and populates the analysis table.
"""
import json
import os
import time
from datetime import datetime, timezone

from . import config
from .db import get_conn, save_analysis
from .analyze import analyze_response


def main():
    """Reprocess unanalyzed query_log rows. Returns an int exit code (0 on
    success, 1 if the API key is missing) rather than calling sys.exit(), so
    callers (e.g. cli.py's main(argv), which always RETURNS an int) can
    propagate it without SystemExit escaping the dispatch guard."""
    config.load_env()
    try:
        config.require_api_key()
    except RuntimeError as e:
        print(f"❌ {e}")
        return 1

    conn = get_conn()
    
    # Get all unanalyzed queries
    rows = conn.execute("""
        SELECT q.id, q.brand_name, q.platform, q.keyword, q.raw_response
        FROM query_log q
        LEFT JOIN analysis a ON a.query_log_id = q.id
        WHERE a.id IS NULL
          AND q.raw_response IS NOT NULL
        ORDER BY q.id
    """).fetchall()
    
    print(f"Found {len(rows)} unanalyzed query_log entries to process")
    
    if not rows:
        print("No unanalyzed queries. Checking total query count...")
        count = conn.execute("SELECT COUNT(*) FROM query_log").fetchone()[0]
        print(f"Total queries in DB: {count}")
        conn.close()
        return 0

    total = len(rows)
    success = 0
    failed = 0
    
    # Group by brand for cleaner progress
    current_brand = None
    for i, row in enumerate(rows, 1):
        qid = row["id"]
        brand_name = row["brand_name"]
        platform = row["platform"]
        keyword = row["keyword"]
        response_text = row["raw_response"]
        
        if brand_name != current_brand:
            current_brand = brand_name
            print(f"\n── [{i}/{total}] {brand_name} ──")
        
        print(f"  [{platform}] \"{keyword}\"...", end=" ", flush=True)
        
        try:
            analysis = analyze_response(brand_name, platform, keyword, response_text)
            
            # Write to DB
            save_analysis(
                query_log_id=qid,
                brand_mentioned=analysis.get("brand_mentioned", False),
                sentiment=analysis.get("sentiment"),
                accuracy=analysis.get("accuracy"),
                competitors=analysis.get("competitors", []),
                visibility_score=analysis.get("visibility_score", 0),
                summary=analysis.get("summary", ""),
            )
            
            mentioned = "✓" if analysis.get("brand_mentioned") else "○"
            score = analysis.get("visibility_score", 0)
            print(f"{mentioned} score={score}")
            success += 1
            
        except Exception as e:
            print(f"✗ Error: {e}")
            failed += 1
        
        time.sleep(0.3)  # Rate limit buffer
    
    print(f"\n{'='*60}")
    print(f"Done: {success} analyzed, {failed} failed out of {total}")
    
    # Now generate the report
    print("\nGenerating report...")
    
    # Get all analyses joined with queries
    analyses_rows = conn.execute("""
        SELECT a.*, q.brand_name, q.platform, q.keyword
        FROM analysis a
        JOIN query_log q ON a.query_log_id = q.id
        ORDER BY q.brand_name, q.id
    """).fetchall()
    
    # Group by brand
    from collections import defaultdict
    brand_analyses = defaultdict(list)
    brand_info = {}
    
    for a in analyses_rows:
        d = dict(a)
        d["brand_mentioned"] = bool(d["brand_mentioned"])
        d["competitors"] = json.loads(d["competitors"]) if isinstance(d["competitors"], str) else (d.get("competitors") or [])
        brand_analyses[d["brand_name"]].append(d)
        brand_info[d["brand_name"]] = {"category": "Uncategorized"}
    
    # Import brands.py for categories, but gracefully handle
    try:
        from .brands import BRANDS
        for b in BRANDS:
            brand_info[b["name"]] = {"category": b["category"]}
    except ImportError:
        pass

    # Render dashboard
    from .dashboard import render_full_dashboard, build_leaderboard, build_competitive_map
    
    # Save output to file
    output_dir = config.get_output_dir()
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "latest-dashboard.txt")
    
    # Capture rich output to string
    from rich.text import Text
    from io import StringIO
    from rich.console import Console as RichConsole
    
    string_io = StringIO()
    file_console = RichConsole(file=string_io, force_terminal=False)
    
    file_console.print(f"AI Search Brand Monitor — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    file_console.print(f"Brands scanned: {len(brand_analyses)}")
    
    leaderboard = build_leaderboard(brand_analyses)
    for entry in leaderboard:
        file_console.print(
            f"  {entry['brand']:20s} → vis:{entry['avg_visibility']:5.1f} "
            f"rate:{entry['mention_rate']:5.0f}% "
            f"👍{entry['positive']} 👎{entry['negative']}"
        )
    
    with open(output_path, "w") as f:
        f.write(string_io.getvalue())
    
    print(f"\n[Dashboard summary saved to {output_path}]")
    
    # Also generate report format
    from .report import generate_report, detect_changes, build_previous_lookup
    
    # For first run, no previous data to compare
    report_lines = []
    report_lines.append(f"AI Search Brand Monitor — INITIAL BASELINE REPORT")
    report_lines.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    report_lines.append(f"Brands: {len(brand_analyses)}")
    report_lines.append(f"Queries analyzed: {total}")
    report_lines.append(f"")
    
    for brand_name in sorted(brand_analyses.keys()):
        analyses = brand_analyses[brand_name]
        mentioned = sum(1 for a in analyses if a["brand_mentioned"])
        avg_score = sum(a["visibility_score"] for a in analyses) / max(len(analyses), 1)
        
        plat_counts = defaultdict(int)
        for a in analyses:
            plat_counts[a["platform"]] += 1
        
        report_lines.append(f"── {brand_name} ──")
        report_lines.append(f"  Visibility: {avg_score:.1f}/100")
        report_lines.append(f"  Mentioned: {mentioned}/{len(analyses)} ({mentioned/max(len(analyses),1)*100:.0f}%)")
        
        # Best platform
        plat_breakdown = {}
        for a in analyses:
            p = a["platform"]
            if p not in plat_breakdown:
                plat_breakdown[p] = {"total": 0, "mentioned": 0, "score_sum": 0}
            plat_breakdown[p]["total"] += 1
            plat_breakdown[p]["mentioned"] += 1 if a["brand_mentioned"] else 0
            plat_breakdown[p]["score_sum"] += a["visibility_score"]
        for plat, stats in plat_breakdown.items():
            avg = stats["score_sum"] / stats["total"] if stats["total"] else 0
            report_lines.append(f"    {plat:12s}: {stats['mentioned']}/{stats['total']} queries, avg score {avg:.0f}")
        
        # Top competitors
        from collections import Counter
        all_comps = []
        for a in analyses:
            all_comps.extend(a.get("competitors", []))
        if all_comps:
            top = Counter(all_comps).most_common(3)
            report_lines.append(f"    Top competitors: {', '.join(f'{c}({n}x)' for c, n in top)}")
        
        report_lines.append("")
    
    report_path = os.path.join(output_dir, "baseline-report.txt")
    with open(report_path, "w") as f:
        f.write("\n".join(report_lines))
    
    print(f"[Baseline report saved to {report_path}]")
    
    # Print full results to stdout for the cron delivery
    print("\n\n=== FULL DASHBOARD ===")
    print("\n".join(report_lines))

    conn.close()
    return 0
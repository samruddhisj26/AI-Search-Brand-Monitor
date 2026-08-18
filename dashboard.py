"""
brand-monitor/dashboard.py — Rich terminal dashboard for brand monitor
The user-facing visual output. Produces a full-screen dashboard with:
- Leaderboard ranked by visibility
- Competitive landscape per category
- Brand cards with recommendations
- Change detection highlights
"""

import json
import os
import sys
from datetime import datetime, timezone
from collections import Counter
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich import box
from rich.columns import Columns


console = Console()


def build_leaderboard(all_results):
    """
    all_results: dict of brand_name -> list of analysis dicts
    Returns sorted list of (brand, avg_visibility, mention_rate, sentiment_summary)
    """
    leaderboard = []
    for brand, analyses in all_results.items():
        if not analyses:
            continue
        total = len(analyses)
        mentioned = [a for a in analyses if a.get("brand_mentioned")]
        visibility_scores = [a.get("visibility_score", 0) for a in analyses]
        avg_visibility = sum(visibility_scores) / total if total else 0
        mention_rate = len(mentioned) / total * 100 if total else 0

        # Sentiment summary
        sentiments = [a["sentiment"] for a in mentioned if a.get("sentiment")]
        pos = sentiments.count("positive")
        neg = sentiments.count("negative")
        neu = sentiments.count("neutral")

        leaderboard.append({
            "brand": brand,
            "avg_visibility": round(avg_visibility, 1),
            "mention_rate": round(mention_rate, 1),
            "positive": pos,
            "negative": neg,
            "neutral": neu,
            "total_mentioned": len(mentioned),
            "total_queries": total,
        })

    leaderboard.sort(key=lambda x: x["avg_visibility"], reverse=True)
    return leaderboard


def build_competitive_map(all_results):
    """
    For each brand, find who their top competitors are across all their queries.
    Returns dict: brand -> list of (competitor, frequency)
    """
    competitive_map = {}
    for brand, analyses in all_results.items():
        if not analyses:
            continue
        competitor_counts = Counter()
        for a in analyses:
            for comp in a.get("competitors", []):
                if comp.lower() != brand.lower():
                    competitor_counts[comp] += 1
        competitive_map[brand] = competitor_counts.most_common(5)
    return competitive_map


def build_category_comparison(all_results, brand_info):
    """Compare brands within the same category."""
    categories = {}
    for brand_name, analyses in all_results.items():
        info = brand_info.get(brand_name, {})
        cat = info.get("category", "Uncategorized")
        if cat not in categories:
            categories[cat] = []
        if analyses:
            scores = [a.get("visibility_score", 0) for a in analyses]
            avg = sum(scores) / len(scores)
            categories[cat].append((brand_name, round(avg, 1)))
    return categories


def render_category_header(category):
    """Render a colored category label."""
    colors = {
        "Design Tools": "cyan",
        "Productivity & Knowledge": "green",
        "Fintech & Payments": "yellow",
        "Deployment & Hosting": "blue",
        "Backend & Database": "magenta",
        "Project Management": "red",
        "Scheduling": "bright_green",
        "Developer Tools": "bright_blue",
        "Forms & No-Code": "bright_magenta",
        "AI Agents": "bright_red",
    }
    return f"[{colors.get(category, 'white')}]{category}[/]"


def render_leaderboard_table(leaderboard):
    """Render the main leaderboard as a Rich table."""
    table = Table(
        title="🏆 AI Search Visibility Leaderboard",
        title_style="bold white",
        box=box.HEAVY_EDGE,
        border_style="bright_blue",
        header_style="bold cyan",
    )
    table.add_column("#", style="dim", width=3)
    table.add_column("Brand", style="bold white", width=18)
    table.add_column("Visibility", justify="right", width=10)
    table.add_column("Mention Rate", justify="right", width=13)
    table.add_column("Positive", justify="right", style="green", width=8)
    table.add_column("Negative", justify="right", style="red", width=8)
    table.add_column("Score Bar", width=20)

    for i, entry in enumerate(leaderboard, 1):
        score = entry["avg_visibility"]
        bar_len = max(1, int(score / 5))
        bar = "█" * bar_len + "░" * (20 - bar_len)

        # Color the bar based on score
        if score >= 40:
            bar_style = "green"
        elif score >= 15:
            bar_style = "yellow"
        else:
            bar_style = "red"

        table.add_row(
            str(i),
            entry["brand"],
            f"{entry['avg_visibility']:.1f}",
            f"{entry['mention_rate']:.0f}%",
            str(entry["positive"]),
            str(entry["negative"]),
            f"[{bar_style}]{bar}[/]",
        )
    return table


def render_category_comparison(categories):
    """Render per-category comparison tables."""
    panels = []
    for cat, brands in sorted(categories.items()):
        if len(brands) < 1:
            continue
        cat_table = Table(box=box.SIMPLE, header_style="bold")
        cat_table.add_column("Brand", width=16)
        cat_table.add_column("Avg Visibility", justify="right", width=14)

        # Sort within category
        sorted_brands = sorted(brands, key=lambda x: x[1], reverse=True)
        for bname, bscore in sorted_brands:
            color = "green" if bscore >= 40 else ("yellow" if bscore >= 15 else "red")
            cat_table.add_row(bname, f"[{color}]{bscore}[/]")

        panel = Panel(
            cat_table,
            title=render_category_header(cat),
            border_style="dim",
            padding=(1, 2),
        )
        panels.append(panel)

    return Columns(panels, equal=False, expand=False)


def render_competitive_grid(competitive_map, brand_info):
    """Render competitive landscape as panels."""
    panels = []
    for brand, competitors in sorted(competitive_map.items()):
        if not competitors:
            continue
        comp_table = Table(box=box.SIMPLE, header_style="dim", show_header=False)
        comp_table.add_column("Competitor", width=20)
        comp_table.add_column("Mentions", justify="right", width=8)

        for comp, count in competitors:
            bar = "▓" * count + "░" * (5 - count)
            comp_table.add_row(comp, f"{bar} {count}")

        cat = brand_info.get(brand, {}).get("category", "")
        panel = Panel(
            comp_table,
            title=f"[bold]{brand}[/]\n{cat}",
            border_style="bright_blue" if competitors else "dim",
            padding=(1, 1),
            width=32,
        )
        panels.append(panel)

    return Columns(panels, equal=False, expand=False)


def render_insights(leaderboard, competitive_map, all_results, brand_info):
    """Generate and render actionable insights per brand."""
    panels = []

    for entry in leaderboard[:5]:  # Top 5 only
        brand = entry["brand"]
        cat = brand_info.get(brand, {}).get("category", "Unknown")
        score = entry["avg_visibility"]
        rate = entry["mention_rate"]

        competitors = competitive_map.get(brand, [])
        top_comp = competitors[0][0] if competitors else "nobody specific"
        comp_count = len(competitors)

        # Generate insights
        if rate < 20:
            insight = (
                f"[red]Low visibility[/] — {brand} barely appears in AI answers "
                f"({rate:.0f}% of queries). "
                f"[yellow]Action:[/] Search is being won by {top_comp}. "
                f"Consider improving SEO for AI visibility — ensure your docs, "
                f"blog, and README are well-structured for AI crawlers."
            )
        elif rate < 50:
            insight = (
                f"[yellow]Moderate visibility[/] ({score}/100 avg). "
                f"Mentioned in {rate:.0f}% of queries but {top_comp} "
                f"appears more consistently. "
                f"[yellow]Action:[/] Increase community-generated content "
                f"(tutorials, comparisons, reviews) that AI models cite."
            )
        else:
            insight = (
                f"[green]Strong visibility[/] ({score}/100 avg, {rate:.0f}% queries). "
                f"Leading in {cat} space against {comp_count} competitors. "
                f"[yellow]Action:[/] Maintain by publishing authoritative content. "
                f"Watch for {top_comp} gaining ground."
            )

        # Build the panel
        panel = Panel(
            insight,
            title=f"[bold]{brand}[/] — {cat}",
            border_style="green" if score >= 40 else ("yellow" if score >= 15 else "red"),
            padding=(1, 2),
            width=60,
        )
        panels.append(panel)

    return Columns(panels, equal=False, expand=False)


def render_share_of_voice(leaderboard, all_results):
    """Render a share-of-voice breakdown."""
    total_mentions = sum(e["total_mentioned"] for e in leaderboard)
    if total_mentions == 0:
        return Panel("No brands were mentioned in any query.", title="Share of Voice", border_style="dim")

    table = Table(box=box.HEAVY_EDGE, header_style="bold cyan")
    table.add_column("Brand", width=18)
    table.add_column("Queries Won", justify="right")
    table.add_column("Share of Voice", justify="right", width=40)

    for entry in leaderboard:
        if entry["total_mentioned"] == 0:
            continue
        pct = entry["total_mentioned"] / total_mentions * 100
        bar_len = max(1, int(pct / 2.5))
        bar = "█" * bar_len
        table.add_row(
            entry["brand"],
            f"{entry['total_mentioned']}/{entry['total_queries']}",
            f"{bar} {pct:.0f}%",
        )

    return Panel(table, title="📊 Share of Voice Across All Brands", border_style="bright_blue")


def render_recommendations_summary(leaderboard, competitive_map, all_results, brand_info):
    """Concise action items for bottom of dashboard."""
    table = Table(box=box.SIMPLE, header_style="bold yellow")
    table.add_column("Brand", width=16)
    table.add_column("Top Gap / Risk", width=50)
    table.add_column("Priority", width=12)

    for entry in leaderboard:
        brand = entry["brand"]
        score = entry["avg_visibility"]
        competitors = competitive_map.get(brand, [])
        top_comp = competitors[0][0] if competitors else "none"
        comp_gap = competitors[0][1] if competitors else 0

        if score < 15:
            gap = f"Invisible in AI answers. {top_comp} dominates ({comp_gap}x mentions)"
            priority = "[red]HIGH[/]"
        elif score < 30:
            gap = f"Low visibility. {top_comp} is pulling ahead ({comp_gap}x mentions)"
            priority = "[yellow]MEDIUM[/]"
        else:
            gap = f"Healthy presence. Monitor {top_comp} for position changes"
            priority = "[green]LOW[/]"

        table.add_row(brand, gap, priority)

    return Panel(table, title="💡 Recommendations Summary", border_style="bright_yellow",
                 title_align="left")


def render_full_dashboard(all_results, brand_info, changes=None):
    """
    Render the complete dashboard.
    all_results: dict of brand_name -> list of analysis dicts
    brand_info: dict of brand_name -> {category, keywords}
    changes: optional list of change strings
    """
    console.clear()

    # ── Header ──
    now = datetime.now(timezone.utc)
    header = Panel(
        f"[bold white]AI Search Brand Monitor[/] — Multi-Brand Dashboard\n"
        f"[dim]Scanned {len(all_results)} brands across "
        f"{sum(len(v) for v in all_results.values())} queries[/]\n"
        f"[dim]{now.strftime('%B %d, %Y at %H:%M UTC')}",
        box=box.HEAVY_EDGE,
        border_style="cyan",
    )
    console.print(header)
    console.print()

    # ── Leaderboard ──
    leaderboard = build_leaderboard(all_results)
    console.print(render_leaderboard_table(leaderboard))
    console.print()

    # ── Share of Voice ──
    sv = render_share_of_voice(leaderboard, all_results)
    console.print(sv)
    console.print()

    # ── Category Comparison ──
    categories = build_category_comparison(all_results, brand_info)
    console.print("[bold]📁 Category Breakdown[/]")
    console.print(render_category_comparison(categories))
    console.print()

    # ── Competitive Grid ──
    competitive_map = build_competitive_map(all_results)
    console.print("[bold]🎯 Competitive Landscape (per brand)[/]")
    console.print(render_competitive_grid(competitive_map, brand_info))
    console.print()

    # ── Insights ──
    console.print("[bold]🔍 Brand Insights & Recommendations[/]")
    console.print(render_insights(leaderboard, competitive_map, all_results, brand_info))
    console.print()

    # ── Recommendations Table ──
    console.print(render_recommendations_summary(leaderboard, competitive_map, all_results, brand_info))
    console.print()

    # ── Footer ──
    footer = Panel(
        "[dim]* Perplexity returns live web results. ChatGPT & Claude API responses have knowledge cutoffs.\n"
        "  Competitors are extracted from AI responses — they may not be exhaustive.[/]",
        border_style="dim",
    )
    console.print(footer)


if __name__ == "__main__":
    # Test with sample data
    from brands import BRANDS
    brand_info = {b["name"]: {"category": b["category"]} for b in BRANDS}

    test_results = {}
    for b in BRANDS[:5]:
        test_results[b["name"]] = [
            {"brand_mentioned": True, "sentiment": "positive", "accuracy": "accurate",
             "competitors": ["CompetitorA", "CompetitorB"], "visibility_score": 65,
             "summary": "Mentioned as a top choice."},
            {"brand_mentioned": False, "sentiment": None, "accuracy": None,
             "competitors": ["CompetitorC"], "visibility_score": 0,
             "summary": "Not mentioned."},
        ]

    render_full_dashboard(test_results, brand_info)
    print("\n[Dashboard rendered successfully]")
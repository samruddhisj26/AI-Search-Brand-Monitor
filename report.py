"""
brand-monitor/report.py — Generate report digest and detect changes
"""

import json
from datetime import datetime, timedelta, timezone


def detect_changes(brand_name, current_analyses, previous_analyses):
    """
    Compare current analyses against previous analyses to detect changes.
    Returns a list of change descriptions.
    """
    changes = []

    for curr in current_analyses:
        plat = curr["platform"]
        kw = curr["keyword"]
        prev = previous_analyses.get((plat, kw))

        if not prev:
            # First time seeing this query
            if curr["brand_mentioned"]:
                changes.append(
                    f"📢 NEW — {brand_name} appeared in {plat}'s response "
                    f"for \"{kw}\" (score: {curr['visibility_score']}/100)"
                )
            continue

        # Compare visibility score
        score_diff = curr["visibility_score"] - prev["visibility_score"]

        if curr["brand_mentioned"] and not prev["brand_mentioned"]:
            changes.append(
                f"🟢 APPEARED — {brand_name} now mentioned in {plat} for \"{kw}\" "
                f"(score: {curr['visibility_score']}/100)"
            )
        elif not curr["brand_mentioned"] and prev["brand_mentioned"]:
            changes.append(
                f"🔴 DISAPPEARED — {brand_name} no longer mentioned in {plat} for \"{kw}\" "
                f"(was: {prev['visibility_score']}/100)"
            )
        elif score_diff >= 20:
            changes.append(
                f"📈 IMPROVED — {brand_name}'s presence in {plat} for \"{kw}\" "
                f"up {score_diff} points ({prev['visibility_score']} → {curr['visibility_score']})"
            )
        elif score_diff <= -20:
            changes.append(
                f"📉 DECLINED — {brand_name}'s presence in {plat} for \"{kw}\" "
                f"down {abs(score_diff)} points ({prev['visibility_score']} → {curr['visibility_score']})"
            )

        # Check sentiment changes
        if curr["brand_mentioned"] and prev["brand_mentioned"]:
            if curr["sentiment"] != prev["sentiment"]:
                changes.append(
                    f"💬 SENTIMENT SHIFT — {brand_name} on {plat} for \"{kw}\": "
                    f"{prev['sentiment']} → {curr['sentiment']}"
                )

            if curr.get("accuracy") != prev.get("accuracy"):
                if curr.get("accuracy") in ("inaccurate", "misattributed"):
                    changes.append(
                        f"⚠️ ACCURACY ISSUE — {brand_name} is {curr['accuracy']} "
                        f"on {plat} for \"{kw}\""
                    )

        # New competitors
        new_comps = set(curr.get("competitors", [])) - set(prev.get("competitors", []))
        if new_comps:
            changes.append(
                f"👀 NEW COMPETITORS — {', '.join(sorted(new_comps))} mentioned "
                f"alongside {brand_name} in {plat} for \"{kw}\""
            )

    return changes


def generate_report(brand_name, current_analyses, changes=None):
    """
    Generate a formatted report text for the brand.
    """
    now = datetime.now(timezone.utc)
    week_start = (now - timedelta(days=7)).strftime("%b %d")
    week_end = now.strftime("%b %d, %Y")

    lines = []
    lines.append(f"╔{'═'*60}╗")
    lines.append(f"║  📊 AI SEARCH BRAND REPORT")
    lines.append(f"║  {brand_name}")
    lines.append(f"║  {week_start} — {week_end}")
    lines.append(f"╚{'═'*60}╝")
    lines.append("")

    # ── Summary stats ──
    total_queries = len(current_analyses)
    mentioned = [a for a in current_analyses if a["brand_mentioned"]]
    not_mentioned = [a for a in current_analyses if not a["brand_mentioned"]]
    mention_rate = len(mentioned) / total_queries * 100 if total_queries else 0
    avg_score = sum(a["visibility_score"] for a in current_analyses) / total_queries if total_queries else 0

    lines.append(f"📈 OVERVIEW")
    lines.append(f"   Queries run:      {total_queries}")
    lines.append(f"   Brand mentioned:  {len(mentioned)}/{total_queries} ({mention_rate:.0f}%)")
    lines.append(f"   Avg visibility:   {avg_score:.0f}/100")
    lines.append("")

    # ── Changes ──
    if changes:
        lines.append(f"⚡ CHANGES SINCE LAST REPORT")
        for c in changes:
            lines.append(f"   {c}")
        lines.append("")

    # ── Platform breakdown ──
    by_platform = {}
    for a in current_analyses:
        by_platform.setdefault(a["platform"], []).append(a)

    for platform in ["chatgpt", "claude", "perplexity"]:
        if platform not in by_platform:
            continue
        results = by_platform[platform]
        plat_name = platform.capitalize()

        plat_mentioned = [r for r in results if r["brand_mentioned"]]
        plat_score = sum(r["visibility_score"] for r in results) / len(results) if results else 0

        lines.append(f"🔍 {plat_name}")
        lines.append(f"   Visibility: {plat_score:.0f}/100 | "
                     f"Mentioned in {len(plat_mentioned)}/{len(results)} queries")

        for r in results:
            if r["brand_mentioned"]:
                sentiment_icon = {"positive": "🟢", "negative": "🔴", "neutral": "⚪", "mixed": "🟡"}.get(r["sentiment"], "⚪")
                comps = ", ".join(r.get("competitors", [])[:3])
                comp_str = f"  [competitors: {comps}]" if comps else ""
                lines.append(
                    f"   {sentiment_icon} \"{r['keyword']}\" — "
                    f"Score: {r['visibility_score']}/100 | "
                    f"Sentiment: {r['sentiment']} {comp_str}"
                )
            else:
                lines.append(f"   ⚪ \"{r['keyword']}\" — Not mentioned")

        lines.append("")

    # ── If never mentioned ──
    if mention_rate == 0:
        lines.append("😕 Brand was not mentioned in any query this cycle.")
        lines.append("   Consider adding different keywords or checking competitors.")
        lines.append("")

    # ── Competitor landscape ──
    all_competitors = []
    for a in current_analyses:
        all_competitors.extend(a.get("competitors", []))
    if all_competitors:
        from collections import Counter
        top_comps = Counter(all_competitors).most_common(8)
        lines.append(f"🏆 COMPETITOR LANDSCAPE (top {len(top_comps)})")
        for comp, count in top_comps:
            bar = "▓" * count
            lines.append(f"   {bar} {comp} ({count}x)")
        lines.append("")

    # ── Recommendations ──
    lines.append(f"💡 RECOMMENDATIONS")
    if mention_rate < 30:
        lines.append(f"   • Consider adding more specific keywords")
        lines.append(f"   • Look at competitor strategy — who's getting mentioned?")
    if any(a.get("accuracy") == "inaccurate" for a in current_analyses):
        lines.append(f"   • Some AI responses contain inaccurate information about the brand")
    if any(a.get("accuracy") == "misattributed" for a in current_analyses):
        lines.append(f"   • Brand is being misattributed — may need PR correction")
    lines.append(f"   • Next scan: +7 days")
    lines.append("")
    lines.append(f"📡 DATA SOURCES")
    lines.append(f"   ChatGPT (gpt-4o)     — API query, knowledge cutoff, no live browse")
    lines.append(f"   Claude (claude-sonnet) — API query, knowledge cutoff, no live browse")
    lines.append(f"   Perplexity (sonar-pro) — API query, search-grounded (live results)")
    lines.append(f"   * Platforms marked 'knowledge cutoff' show training data only.")

    lines.append("")
    lines.append(f"───")
    lines.append(f"AI Search Brand Monitor · Samruddhi's Project")
    lines.append(f"Generated: {now.strftime('%Y-%m-%d %H:%M UTC')}")

    return "\n".join(lines)


def build_previous_lookup(db_analyses):
    """Build a dict of (platform, keyword) -> previous analysis from DB results."""
    lookup = {}
    for a in db_analyses:
        if a.get("platform") and a.get("keyword"):
            key = (a["platform"], a["keyword"])
            # Take the first one (already sorted by time desc, so this is the most recent)
            if key not in lookup:
                lookup[key] = {
                    "brand_mentioned": bool(a["brand_mentioned"]),
                    "sentiment": a["sentiment"],
                    "accuracy": a["accuracy"],
                    "competitors": json.loads(a["competitors"]) if isinstance(a["competitors"], str) else (a["competitors"] or []),
                    "visibility_score": a["visibility_score"],
                    "summary": a["summary"],
                }
    return lookup


if __name__ == "__main__":
    # Test
    test = [
        {"platform": "chatgpt", "keyword": "best AI agent", "brand_mentioned": True,
         "sentiment": "positive", "accuracy": "accurate", "competitors": ["OpenClaw"],
         "visibility_score": 75, "summary": "Recommended highly"},
        {"platform": "chatgpt", "keyword": "AI tools", "brand_mentioned": False,
         "sentiment": None, "accuracy": None, "competitors": [], "visibility_score": 0,
         "summary": "Not mentioned"},
    ]
    print(generate_report("Test Brand", test))
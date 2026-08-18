"""
brand-monitor/analyze.py — Analyze AI responses for brand mention, sentiment, competitors
"""

import json
import os
import time
import urllib.request
import urllib.error

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE = "https://openrouter.ai/api/v1/chat/completions"
ANALYSIS_MODEL = os.environ.get("ANALYSIS_MODEL", "openai/gpt-4o-mini")

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "HTTP-Referer": "https://github.com/samruddhi/brand-monitor",
    "X-Title": "Brand Monitor Analysis",
}


def analyze_response(brand_name, platform, keyword, response_text):
    """
    Analyze an AI platform's response for brand visibility.
    Returns a dict with structured analysis results.
    """
    if not response_text:
        return {
            "brand_mentioned": False,
            "sentiment": None,
            "accuracy": None,
            "competitors": [],
            "visibility_score": 0,
            "summary": "No response to analyze.",
        }

    system_prompt = (
        "You are a brand monitoring analyst. Your job is to analyze an AI assistant's "
        "response to determine how a specific brand appears in it.\n\n"
        "Return a JSON object with these fields:\n"
        "- brand_mentioned: boolean — was the brand name mentioned in the response?\n"
        "- sentiment: string or null — 'positive', 'negative', 'neutral', 'mixed', or null if not mentioned\n"
        "- accuracy: string or null — 'accurate' (correctly described), 'misattributed' "
        "(credited for something it didn't do), 'inaccurate' (wrong info), or null if not mentioned\n"
        "- competitors: array of strings — names of competing products/services mentioned alongside or instead of the brand\n"
        "- visibility_score: integer 0-100 — how prominently the brand appears. "
        "0 = not mentioned, 1-30 = brief mention, 31-60 = discussed with context, "
        "61-100 = featured prominently or recommended\n"
        "- summary: string — 1-2 sentence plain-language summary of how the brand appeared\n\n"
        "Respond with ONLY the JSON object, no other text."
    )

    user_prompt = (
        f"Brand to track: {brand_name}\n"
        f"Keyword queried: \"{keyword}\"\n"
        f"AI platform: {platform}\n\n"
        f"AI response to analyze:\n---\n{response_text}\n---"
    )

    payload = json.dumps({
        "model": ANALYSIS_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 512,
        "temperature": 0.1,  # Low temp for consistent extraction
    }).encode("utf-8")

    req = urllib.request.Request(
        OPENROUTER_BASE,
        data=payload,
        headers=HEADERS,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        raw = result["choices"][0]["message"]["content"]

        # Parse the JSON response
        # The model might wrap in markdown code blocks
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()

        parsed = json.loads(raw)
        return {
            "brand_mentioned": bool(parsed.get("brand_mentioned", False)),
            "sentiment": parsed.get("sentiment"),
            "accuracy": parsed.get("accuracy"),
            "competitors": parsed.get("competitors", []),
            "visibility_score": int(parsed.get("visibility_score", 0)),
            "summary": parsed.get("summary", ""),
        }

    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        return {
            "brand_mentioned": False,
            "sentiment": None,
            "accuracy": None,
            "competitors": [],
            "visibility_score": 0,
            "summary": f"Analysis failed: {e}",
        }
    except (json.JSONDecodeError, KeyError) as e:
        return {
            "brand_mentioned": False,
            "sentiment": None,
            "accuracy": None,
            "competitors": [],
            "visibility_score": 0,
            "summary": f"Could not parse analysis output: {e}",
        }


def analyze_all(brand_name, query_results):
    """Analyze all query results for a brand."""
    analyses = []
    for q in query_results:
        print(f"  Analyzing [{q['platform']}] \"{q['keyword']}\"...")
        analysis = analyze_response(
            brand_name,
            q["platform"],
            q["keyword"],
            q.get("response"),
        )
        analysis["platform"] = q["platform"]
        analysis["keyword"] = q["keyword"]
        analyses.append(analysis)
        time.sleep(0.5)  # Rate limit buffer
    return analyses


if __name__ == "__main__":
    # Test
    test_response = (
        "There are several great AI coding agents in 2026. "
        "Hermes Agent by Nous Research is a popular choice for developers who want "
        "a self-improving agent with persistent memory. It compares well against "
        "OpenClaw and Claude Code. I'd recommend Hermes for its skill-learning capabilities."
    )
    result = analyze_response("Hermes Agent", "chatgpt", "best AI coding agent", test_response)
    print(json.dumps(result, indent=2))
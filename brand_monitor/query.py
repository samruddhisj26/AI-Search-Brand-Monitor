"""
brand-monitor/query.py — Query AI platforms via OpenRouter API
"""

import json
import time
import urllib.request
import urllib.error

from . import config

OPENROUTER_BASE = "https://openrouter.ai/api/v1/chat/completions"

# Model mapping per platform
PLATFORM_MODELS = {
    "chatgpt": "openai/gpt-4o",           # Closest to ChatGPT web
    "claude": "anthropic/claude-sonnet-4", # Closest to Claude web
    "perplexity": "perplexity/sonar-pro",  # Perplexity's search-grounded model
}

# System prompts that mimic how each platform presents itself
PLATFORM_PROMPTS = {
    "chatgpt": (
        "You are ChatGPT, a helpful AI assistant. Answer the user's question "
        "concisely and informatively based on your training data."
    ),
    "claude": (
        "You are Claude, an AI assistant created by Anthropic. Answer the user's "
        "question helpfully and accurately."
    ),
    "perplexity": (
        "You are Perplexity AI, a search-grounded assistant. Provide accurate, "
        "up-to-date information with citations where relevant. Be thorough."
    ),
}

# The keywords/queries we'll test for each brand
DEFAULT_KEYWORDS = [
    "best AI coding agent 2026",
    "open source AI agent comparison",
    "top AI developer tools",
    "AI agent for Discord and Telegram",
]


def query_openrouter(platform, user_prompt, timeout=30, max_retries=2):
    """Query an AI platform via OpenRouter and return the response text."""
    model = PLATFORM_MODELS.get(platform)
    if not model:
        raise ValueError(f"Unknown platform: {platform}. Available: {list(PLATFORM_MODELS.keys())}")

    system_prompt = PLATFORM_PROMPTS.get(platform, "You are a helpful AI assistant.")

    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 1024,
        "temperature": 0.7,
    }).encode("utf-8")

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            req = urllib.request.Request(
                OPENROUTER_BASE,
                data=payload,
                headers=config.get_headers(),
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            # Extract the response text
            content = result["choices"][0]["message"]["content"]
            return content.strip()

        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            last_error = str(e)
            if attempt < max_retries:
                wait = (attempt + 1) * 2
                print(f"  ⚠ Query failed (attempt {attempt+1}), retrying in {wait}s: {e}")
                time.sleep(wait)
            continue
        except (KeyError, json.JSONDecodeError) as e:
            last_error = f"Parse error: {e}, raw: {result if 'result' in dir() else 'N/A'}"
            break

    raise RuntimeError(f"Query failed after {max_retries + 1} attempts: {last_error}")


def run_queries(brand_name, keywords=None):
    """
    Query all platforms for a brand across given keywords.
    Returns list of dicts: {platform, keyword, prompt, response, error}
    """
    if keywords is None:
        # Generate brand-specific keywords
        keywords = [
            f"what is the best {brand_name} alternative",
            f"top {brand_name} competitors 2026",
            f"review of {brand_name} for developers",
            f"{brand_name} vs other AI tools",
            f"best open source AI agents {brand_name}",
        ]

    results = []
    for platform in PLATFORM_MODELS:
        print(f"\n  [{platform}] Querying {len(keywords)} keywords...")
        for kw in keywords:
            prompt = f"Search the web and tell me: {kw}"
            print(f"    ↪ \"{kw}\"")
            try:
                response = query_openrouter(platform, prompt)
                results.append({
                    "platform": platform,
                    "keyword": kw,
                    "prompt": prompt,
                    "response": response,
                    "error": None,
                })
                print(f"    ✓ Got response ({len(response)} chars)")
            except Exception as e:
                results.append({
                    "platform": platform,
                    "keyword": kw,
                    "prompt": prompt,
                    "response": None,
                    "error": str(e),
                })
                print(f"    ✗ Failed: {e}")
            time.sleep(1)  # Rate limit buffer

    return results

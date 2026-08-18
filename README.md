# AI Search Brand Monitor

Track how brands appear in ChatGPT, Claude, and Perplexity answers. Multi-brand competitive dashboard with visibility scores, share of voice, competitive landscape, and actionable recommendations.

## How it works

Every week, the monitor queries 3 AI platforms (ChatGPT, Claude, Perplexity) with brand-specific keywords, analyzes the responses for brand mentions, and generates a competitive dashboard.

### Pipeline
1. **Query** — Sends keyword questions to AI platforms via OpenRouter API
2. **Analyze** — GPT-4o-mini extracts brand presence, sentiment, competitors, visibility score
3. **Report** — Rich terminal dashboard with leaderboard, share of voice, category breakdowns
4. **Detect** — Compares against previous cycle to detect changes (appeared/disappeared/sentiment shifts)

### Supported platforms
| Platform | Model | Web Search? |
|---|---|---|
| ChatGPT | GPT-4o (via OpenRouter) | Knowledge cutoff |
| Claude | Claude Sonnet (via OpenRouter) | Knowledge cutoff |
| Perplexity | Sonar Pro (via OpenRouter) | ✅ Live web results |

## Quick start

```bash
# Install dependencies
pip install rich

# Set your API key
export OPENROUTER_API_KEY="sk-or-..."

# Run a full scan
python3 runner.py

# Or scan a single brand
python3 runner.py --brand "Figma"
```

## Add a brand
Edit `brands.py` and add to the `BRANDS` list:
```python
{
    "name": "YourBrand",
    "category": "Your Industry",
    "keywords": ["keyword1", "keyword2", "keyword3"],
}
```

## Data model
SQLite database (`brand_monitor.db`):
- `query_log` — Raw AI responses
- `analysis` — Extracted brand mentions, sentiment, competitors, visibility scores
- `reports` — Generated report summaries

## Dependencies
- Python 3.10+
- OpenRouter API key
- `rich` (for terminal dashboard)

## Roadmap
- [x] Multi-brand scanning (10 brands)
- [x] Competitive landscape extraction
- [x] Share of voice analysis
- [x] Change detection between cycles
- [ ] Web dashboard for self-service
- [ ] Google AI Overviews integration
- [ ] Per-brand alerting
- [ ] Stripe billing → SaaS

## License
MIT
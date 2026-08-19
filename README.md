# AI Search Brand Monitor

A CLI that asks GPT-4o, Claude Sonnet 4, and Perplexity Sonar Pro — **all accessed through the OpenRouter API** — a set of brand-related questions, then uses an LLM to score each response for brand mentions, sentiment, accuracy, and competitors. It renders the results as a terminal dashboard and a local web dashboard.

## What this is not

This tool does **not** scrape or automate the consumer ChatGPT, Claude, or Perplexity apps. It sends prompts to the underlying models via OpenRouter, with a system prompt asking each model to answer as if it were that platform. That means:

- No personalization, no browsing history, no account context — you get what the base model produces from a cold prompt.
- No product-side retrieval augmentation, except Perplexity's own model does live web search as part of how it's served on OpenRouter; ChatGPT's and Claude's responses come from training-data knowledge, not live browsing.
- Results will not necessarily match what a person sees by typing the same question into chatgpt.com, claude.ai, or perplexity.ai.

The scoring itself is also an LLM judgment, not ground truth: analysis runs through `openai/gpt-4o-mini` by default (override with `ANALYSIS_MODEL`), so "sentiment" and "visibility score" are one model's read of another model's text, not a verified fact. Content retrieved from the web — especially Perplexity's live search results — can contain text shaped to influence scoring outcomes. Treat scores as directional signal for trends within a single run, not as authoritative measurement or ground truth.

With that understood, it's a useful, cheap way to sanity-check how a brand tends to come up across several models' training data and Perplexity's live search — not a monitoring feed of the actual consumer products.

## Platform → model mapping

| "Platform" label | Model queried (via OpenRouter) | Live web search? |
|---|---|---|
| ChatGPT | `openai/gpt-4o` | No — training-data knowledge only |
| Claude | `anthropic/claude-sonnet-4` | No — training-data knowledge only |
| Perplexity | `perplexity/sonar-pro` | Yes — Perplexity's model does live search |

## Install

Not published to PyPI — install from a clone.

```bash
git clone https://github.com/samruddhisj26/AI-Search-Brand-Monitor.git
cd AI-Search-Brand-Monitor

# Primary: pipx (isolated environment, puts `brand-monitor` on your PATH)
pipx install .
pipx ensurepath  # adds pipx's bin dir to PATH if it isn't already there — restart your shell (or open a new terminal) afterward

# Alternative: into a virtualenv
python3 -m venv .venv && source .venv/bin/activate
pip install .
```

Requires Python 3.9+.

## Configure

You need an OpenRouter API key (https://openrouter.ai/keys). Either:

```bash
cp .env.example .env
# edit .env and set OPENROUTER_API_KEY
```

or just export it directly — both work, and a real exported variable always wins over `.env`:

```bash
export OPENROUTER_API_KEY="sk-or-..."
```

| Env var | Default | Purpose |
|---|---|---|
| `OPENROUTER_API_KEY` | *(required)* | OpenRouter API key used for both querying and analysis |
| `ANALYSIS_MODEL` | `openai/gpt-4o-mini` | Model used to score each response |
| `BRAND_MONITOR_DB` | `./brand_monitor.db` | SQLite database path |
| `BRAND_MONITOR_OUTPUT` | `./output` | Report output directory |

## Where data lands

The database and reports are resolved **relative to the directory you run `brand-monitor` from**, not relative to the install location. Run it from two different directories and you get two separate databases. If you want a stable location regardless of cwd, set `BRAND_MONITOR_DB` and `BRAND_MONITOR_OUTPUT` to absolute paths, or pass `--db` explicitly on every invocation.

## Cost warning

`scan` makes real, paid OpenRouter API calls. Each bundled brand has 3 keywords, queried against all 3 platforms (9 query calls), plus one analysis call per response (9 more) — 18 calls per brand. Scanning all 10 bundled brands is roughly 180 paid API calls in one run. Use `--brand NAME` to scan a single brand while you're getting a feel for cost.

## Commands

All commands accept a global `--db PATH` to override the database location — it works whether you put it before or after the subcommand (`brand-monitor --db PATH scan` or `brand-monitor scan --db PATH`). Note that a typo in the path will create a new empty database rather than raise an error.

| Command | Flags | What it does |
|---|---|---|
| `scan` | `--brand NAME`, `--db PATH` | Queries all 3 platforms and analyzes the responses. Scans every tracked brand, or just one with `--brand`. Requires `OPENROUTER_API_KEY`. |
| `serve` | `--port N` (default 8766), `--db PATH` | Starts the local web dashboard, bound to `127.0.0.1` only (not configurable). |
| `reprocess` | `--db PATH` | Re-runs analysis over rows already in `query_log` without re-querying the platforms. Requires `OPENROUTER_API_KEY`. |
| `init-db` | `--db PATH` | Creates the database schema if it doesn't exist and prints the resolved path. No API key needed. |
| `brands` | `--db PATH` | Lists tracked brands with their categories and keywords. No API key needed. |

Global flags: `--version` prints the installed version; `--db PATH` sets the database path for any command.

There is no `report` subcommand — a terminal dashboard and SQLite report rows are generated automatically as part of `scan` and `reprocess`.

### Quickstart

```bash
brand-monitor init-db          # create the schema, print its path
brand-monitor brands           # see what's tracked, no API key needed
brand-monitor scan --brand "Figma"   # scan one brand
brand-monitor serve            # open http://127.0.0.1:8766
```

## Scheduling

There is no built-in scheduler. `scan` runs on demand, once, and exits. If you want recurring monitoring, schedule it yourself, e.g. with cron:

```cron
0 9 * * 1 cd /path/to/project && /path/to/brand-monitor scan
```

## Adding a brand

There's no config file for this yet — edit `brand_monitor/brands.py` directly and add an entry to the `BRANDS` list:

```python
{
    "name": "YourBrand",
    "category": "Your Industry",
    "keywords": ["keyword1", "keyword2", "keyword3"],
}
```

## Data model

SQLite database (default `./brand_monitor.db`):
- `query_log` — raw responses from each platform
- `analysis` — extracted brand mentions, sentiment, competitors, visibility scores
- `reports` — generated report summaries

## Tests

A smoke-test suite lives under `tests/`. Run it with:

```bash
pip install -e ".[dev]"
pytest
```

## Requirements

- Python 3.9+
- An OpenRouter API key

## Roadmap

- [x] Multi-brand scanning (10 bundled brands)
- [x] Competitive landscape extraction
- [x] Share of voice analysis
- [x] Change detection between cycles
- [x] Web dashboard (`brand-monitor serve`)
- [ ] Config-driven brand list (no source edit required)
- [ ] Google AI Overviews integration
- [ ] Per-brand alerting
- [ ] Scheduled/recurring runs built into the CLI

## License

MIT — see `LICENSE`.

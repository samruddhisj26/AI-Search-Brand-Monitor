# brand-monitor (Claude Code plugin)

Wraps the `brand-monitor` CLI so you can drive it from slash commands inside Claude Code. This plugin does not reimplement any logic -- every command shells out to the already-installed `brand-monitor` binary.

## Prerequisite

`brand-monitor` must already be installed and on your `PATH` before using this plugin, e.g.:

```
pipx install ai-search-brand-monitor
```

The plugin manifest has no way to declare an external binary dependency, so run `/brand-monitor:status` first in any new session to confirm the CLI is installed, the `OPENROUTER_API_KEY` environment variable is set, and check what data already exists in your current directory.

## Install

```
/plugin marketplace add samruddhisj26/AI-Search-Brand-Monitor
/plugin install brand-monitor@brand-monitor-tools
```

(Or, from a local clone, add the marketplace by path.)

## Commands

| Command | Cost | What it does |
|---|---|---|
| `/brand-monitor:status` | Free | Checks the CLI is installed, the API key is set (never prints the key itself), and whether a database or report already exist in the current directory. Run this first. |
| `/brand-monitor:scan <brand>` | **Spends money** -- ~18 OpenRouter API calls per brand | Runs `brand-monitor scan --brand "<brand>"` for one named brand. Requires an explicit brand name; will not run against all 10 bundled brands silently. |
| `/brand-monitor:dashboard [port]` | Free | Starts `brand-monitor serve` in the background (default port 8766) and reports `http://127.0.0.1:<port>`. Does not block your session. Reads the database from the current working directory. |
| `/brand-monitor:report` | Free | Reads and summarizes `output/latest-dashboard.txt` from the current directory. Does not call the CLI. If missing, tells you to run a scan -- `reprocess` is not a free substitute. |

## Notes

- The database (`brand_monitor.db`) and report file (`output/latest-dashboard.txt`) are both resolved from the **current working directory** you run Claude Code in (or overridden with `--db` / `$BRAND_MONITOR_DB` / `$BRAND_MONITOR_OUTPUT`). Run commands from the same directory you scanned in, or you'll see empty results.
- `brand-monitor scan` and `brand-monitor reprocess` both make paid OpenRouter API calls. Only `status` and `report` are free, and `dashboard` is free to start (it only reads existing data).
- Bundled brand names: Figma, Notion, Stripe, Vercel, Supabase, Linear, Cal.com, Raycast, Tally, Hermes Agent.

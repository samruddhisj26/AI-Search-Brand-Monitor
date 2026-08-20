---
description: Run a live brand-monitor scan for one brand against AI search platforms (spends OpenRouter API credits)
argument-hint: "<brand-name>"
disable-model-invocation: true
allowed-tools: Bash(brand-monitor scan *), Bash(which *)
---

## Preflight (safe, no API calls)

- brand-monitor on PATH: !`which brand-monitor || echo "NOT FOUND — install brand-monitor before using this command" || true`

## Your task

The user ran `/brand-monitor:scan` with arguments: `$ARGUMENTS`

**STOP AND WARN BEFORE RUNNING ANYTHING.** `brand-monitor scan` makes REAL, PAID OpenRouter API calls — roughly **18 calls for a single brand** (3 keywords x 3 platforms, x2 for the analysis pass). Before invoking the CLI, tell the user plainly that this will spend money and roughly how many calls it involves, and get a clear go-ahead from the conversation context before proceeding (if the user already explicitly named a brand and asked to scan it, that itself counts as consent — don't make them confirm twice).

**Brand argument is required.** Look at `$ARGUMENTS`:
- If it is empty or blank, DO NOT run `brand-monitor scan` with no `--brand` flag. A bare `brand-monitor scan` scans ALL 10 bundled brands (Figma, Notion, Stripe, Vercel, Supabase, Linear, Cal.com, Raycast, Tally, Hermes Agent) at roughly 10x the cost (~180 API calls). Instead, ask the user which single brand they want to scan and stop there.
- If it is present, treat it as the brand name.

If the preflight above shows "NOT FOUND", tell the user brand-monitor is not installed and stop — do not attempt to run the scan.

Once you have a brand name and have warned about cost, run:

```
brand-monitor scan --brand "<brand name>"
```

using the Bash tool.

### Handling the result

- **Exit code 0**: Success. Summarize the resulting dashboard output for the user in plain language (which platforms mentioned the brand, sentiment, notable competitors) — do NOT dump the raw ANSI-formatted terminal output verbatim.
- **Exit code 2**: Usage/config error — almost always a missing API key. If the output matches "Error: OPENROUTER_API_KEY is not set. Copy .env.example to .env and add your key, or export OPENROUTER_API_KEY=... before running.", show the user that exact fix.
- **Exit code 1**: Runtime failure. Show the relevant error output and suggest checking network connectivity or the OpenRouter API status; do not retry automatically since retries also cost money.
- **Exit code 130**: The scan was interrupted (e.g. Ctrl-C). Report that it was cancelled partway and note that any calls already made were still billed.

Never run `brand-monitor scan` more than once per invocation of this command without the user explicitly asking again — each run costs money.

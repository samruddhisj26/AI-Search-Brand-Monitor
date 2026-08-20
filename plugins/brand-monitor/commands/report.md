---
description: Show the most recent brand-monitor scan report from disk (free, no API calls)
argument-hint: ""
disable-model-invocation: true
allowed-tools: Bash(test *), Bash(cat *), Bash(pwd)
---

## Preflight (safe, no API calls)

- Current working directory: !`pwd || true`
- Report file exists at ./output/latest-dashboard.txt: !`if [ -f "./output/latest-dashboard.txt" ]; then echo "yes"; else echo "no"; fi || true`

## Your task

This command is completely free -- it only reads a file already written to disk by a previous `brand-monitor scan` run. It never calls `brand-monitor` and never spends API credits.

The `brand-monitor` CLI has no `report` subcommand and no `results` subcommand -- this command works by reading the plain-text file `output/latest-dashboard.txt` from the current working directory directly with the Bash tool (or the `$BRAND_MONITOR_OUTPUT` directory if that environment variable is set instead of the default `output/`).

Based on the preflight check above:

- If the file exists ("yes"): read `./output/latest-dashboard.txt` with the Bash tool (e.g. `cat ./output/latest-dashboard.txt`) and summarize it for the user in plain language -- key findings, which brand(s) it covers, sentiment/mentions per platform. Do not just dump the raw file unless the user asks for the raw text.
- If the file does not exist ("no"): tell the user plainly that no scan report is available yet in this directory, and that a scan has to run first -- point them at `/brand-monitor:scan <brand-name>`. **Do not suggest `brand-monitor reprocess` as a free or cheap alternative** -- it still runs a paid analysis API call per stored database row, it is not free, and it does not replace running a scan when there is no report file at all.

Never invoke `brand-monitor scan`, `brand-monitor reprocess`, or `brand-monitor serve` from this command.

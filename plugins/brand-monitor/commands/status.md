---
description: Check whether the brand-monitor CLI is installed and ready, with no API calls and no spending
argument-hint: ""
disable-model-invocation: true
allowed-tools: Bash(brand-monitor *), Bash(which *), Bash(test *), Bash(printenv *), Bash(pwd)
---

## Diagnostic context (gathered before this prompt, safe and free — no API calls)

- brand-monitor on PATH: !`which brand-monitor || echo "NOT FOUND"`
- brand-monitor version: !`brand-monitor --version 2>&1 || echo "unavailable"`
- OPENROUTER_API_KEY set: !`printenv OPENROUTER_API_KEY >/dev/null 2>&1 && echo "set" || echo "not set"`
- Current working directory: !`pwd || true`
- Database exists at ./brand_monitor.db: !`if [ -f "./brand_monitor.db" ]; then echo "yes"; else echo "no"; fi || true`
- Past scan report exists at ./output/latest-dashboard.txt: !`if [ -f "./output/latest-dashboard.txt" ]; then echo "yes"; else echo "no"; fi || true`

## Your task

Using ONLY the diagnostic context gathered above (do not run any additional commands, and never print the value of `OPENROUTER_API_KEY` itself — only whether it is set), report a clear readiness summary to the user:

1. **CLI installed?** If "NOT FOUND", tell the user to install it first (it should already be installed via `pipx install` per the project README) — do not proceed with other advice until this is fixed.
2. **API key set?** If "not set", explain that `scan` and `reprocess` will fail with exit code 2 until they run `export OPENROUTER_API_KEY=...` or create a `.env` from `.env.example`. Never echo any key value.
3. **Database present?** If "no", explain that no scan has been run yet from this directory (remember: the database path is resolved from the current working directory, or overridden with `--db` / `$BRAND_MONITOR_DB`).
4. **Past report present?** If "yes", mention that `/brand-monitor:report` can show it for free right now. If "no", mention that a scan must run first before there is anything to report.

End with a short "next step" line naming the single most useful thing the user should do next (e.g. install the CLI, set the API key, run `/brand-monitor:scan <brand>`, or run `/brand-monitor:report`).

Do not run `brand-monitor scan`, `brand-monitor reprocess`, or `brand-monitor serve` from this command — this command is diagnostic only and must never spend money or start a background process.

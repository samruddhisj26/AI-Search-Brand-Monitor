---
description: Start the brand-monitor web dashboard in the background and report its URL (free, no API calls)
argument-hint: "[port]"
disable-model-invocation: true
allowed-tools: Bash(brand-monitor serve *), Bash(test *), Bash(pwd)
---

## Preflight (safe, no API calls)

- Current working directory: !`pwd || true`
- Database exists at ./brand_monitor.db in this directory: !`if [ -f "./brand_monitor.db" ]; then echo "yes"; else echo "no"; fi || true`

## Your task

The user ran `/brand-monitor:dashboard` with arguments: `$ARGUMENTS` (optionally a port number; default is `8766`).

**Important: with no database present, `brand-monitor serve` does NOT start with an empty dashboard.** It exits immediately with code 1 and prints "Database not found ... Run the scanner first: brand-monitor scan" — it never binds the port at all.

**Critical: `brand-monitor serve` blocks forever (`serve_forever()`) until interrupted, if it starts successfully.** You MUST run it as a background process using the Bash tool's `run_in_background` option. Never run it as a normal foreground Bash call — that would hang this entire session indefinitely.

Steps:

1. Determine the port: use `$ARGUMENTS` if a valid port number was given, otherwise default to `8766`.
2. Look at the preflight database check above. If it says "no", tell the user BEFORE attempting to start the server: `brand-monitor serve` reads `./brand_monitor.db` from the current working directory shown above, and if it's missing here, `serve` will exit immediately with "Database not found" rather than starting anything. Suggest they either `cd` to the directory where they scanned, or run `/brand-monitor:scan <brand>` first (note: that spends money).
3. Start the server in the background:

   ```
   brand-monitor serve --port <port>
   ```

   using the Bash tool with `run_in_background: true`.

4. **You must verify the process actually came up before reporting a URL — do not assume it.** Because `serve` blocks forever on success, "still running" is itself the success signal; a process that already exited is the failure signal. Do a single bounded check, not open-ended polling: wait a couple of seconds, then check whether the background task has already exited.

### Handling the result

- **Still running after the brief wait**: this is success — it bound the port. Report the URL to the user: `http://127.0.0.1:<port>` (the server only binds to localhost — it is not reachable from other machines, and the port is the only thing that's configurable). Then tell the user explicitly how to stop it later: the background process needs to be terminated (e.g. by stopping the background task in this session, or by finding and killing the `brand-monitor serve` process) — it will otherwise keep running after this conversation ends.
- **Exited with code 1**: the database was not found (see the "Important" note above). Tell the user plainly that no dashboard is running and no URL was ever bound — do NOT report a URL. Point them at running a scan first (`/brand-monitor:scan <brand>` — spends money) or at the directory that already has `brand_monitor.db`.
- **Exited with any other non-zero code**: treat it the same as a failure — show the relevant error output, do not report a URL, and do not retry automatically.

Never report a URL without having confirmed the process is still alive after the brief wait.

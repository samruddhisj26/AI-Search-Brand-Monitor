"""
brand_monitor/cli.py — Console-script entry point for `brand-monitor`.

Registered in pyproject.toml as:

    [project.scripts]
    brand-monitor = "brand_monitor.cli:main"

Design notes:
  * `main(argv=None)` never calls sys.exit() itself (argparse's own
    --help/-h/usage-error handling is the one exception — that's standard
    argparse behavior and still yields the right process exit code). It
    always returns an int; the generated console script does
    `sys.exit(main())`.
  * `--help`, `--version`, and the `brands` subcommand must work with no
    OPENROUTER_API_KEY set and no database present — they never import the
    network/API modules and never touch config.require_api_key().
  * Heavy modules (rich, http.server, the query/analyze pipeline) are
    imported lazily inside each subcommand handler, not at module import
    time, so `brand-monitor --help` stays fast and doesn't require
    optional dependencies to be importable.
"""

import argparse
import sys

from . import config

EXIT_OK = 0
EXIT_RUNTIME_ERROR = 1
EXIT_USAGE_ERROR = 2
EXIT_INTERRUPTED = 130


def _build_parser():
    # Shared `--db` definition inherited by every subparser, so both
    # `brand-monitor --db PATH <command>` (top-level parser, below) and
    # `brand-monitor <command> --db PATH` (this parent, via `parents=[]`)
    # work. Kept on a distinct dest (db_sub) from the top-level's (db_global)
    # so argparse can't silently clobber one with the other's unset default —
    # see the resolution logic in main().
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--db",
        dest="db_sub",
        metavar="PATH",
        default=None,
        help=(
            "Path to the SQLite database file. Overrides $BRAND_MONITOR_DB "
            "and the default ./brand_monitor.db. May also be given before "
            "the subcommand (brand-monitor --db PATH <command>); if given "
            "in both places, this one wins."
        ),
    )

    parser = argparse.ArgumentParser(
        prog="brand-monitor",
        description=(
            "Track how brands appear in ChatGPT, Claude, and Perplexity "
            "answers. Multi-brand competitive dashboard with visibility "
            "scores, share of voice, competitive landscape, and actionable "
            "recommendations."
        ),
    )
    parser.add_argument(
        "--db",
        dest="db_global",
        metavar="PATH",
        default=None,
        help=(
            "Path to the SQLite database file. Overrides $BRAND_MONITOR_DB "
            "and the default ./brand_monitor.db. Applies to every "
            "subcommand; can also be given after the subcommand instead."
        ),
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print the installed version and exit.",
    )

    subparsers = parser.add_subparsers(dest="command")

    scan_parser = subparsers.add_parser(
        "scan",
        parents=[common],
        help="Query AI platforms and analyze brand visibility.",
        description=(
            "Run brand-visibility queries against AI search platforms and "
            "analyze the responses. Requires OPENROUTER_API_KEY."
        ),
    )
    scan_parser.add_argument(
        "--brand",
        metavar="NAME",
        help=(
            "Scan a single brand by name (case-insensitive). "
            "Scans every tracked brand if omitted."
        ),
    )

    serve_parser = subparsers.add_parser(
        "serve",
        parents=[common],
        help="Start the local web dashboard.",
        description=(
            "Start the read-only web dashboard and block until interrupted. "
            "Always binds to 127.0.0.1 (not configurable — deliberately "
            "kept local-only)."
        ),
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=8766,
        metavar="N",
        help="Port to listen on (default: 8766).",
    )

    subparsers.add_parser(
        "reprocess",
        parents=[common],
        help="Re-analyze existing query_log rows and regenerate reports.",
        description=(
            "Re-run the analysis step over rows already stored in "
            "query_log, without re-querying AI platforms. "
            "Requires OPENROUTER_API_KEY."
        ),
    )

    subparsers.add_parser(
        "init-db",
        parents=[common],
        help="Create or verify the SQLite database schema.",
        description=(
            "Create the database schema if it doesn't exist yet, and print "
            "the resolved database path. No API key required."
        ),
    )

    subparsers.add_parser(
        "brands",
        parents=[common],
        help="List the tracked brands with their categories and keywords.",
        description=(
            "Print the tracked brands, their categories, and their keyword "
            "sets. Pure local data — works with no API key and no database."
        ),
    )

    return parser


def _cmd_scan(args):
    from .brands import BRANDS
    from .dashboard import render_full_dashboard
    from .db import init_db
    from .runner import process_brand, run_multi_brand_cycle

    try:
        config.require_api_key()
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_USAGE_ERROR

    if args.brand:
        matches = [b for b in BRANDS if b["name"].lower() == args.brand.lower()]
        if not matches:
            # Preserves runner.py's original single-brand-mode message
            # and behavior exactly.
            print(f"❌ Brand '{args.brand}' not found in brands.py")
            return EXIT_RUNTIME_ERROR
        init_db()
        analyses = process_brand(matches[0])
        brand_info = {matches[0]["name"]: {"category": matches[0]["category"]}}
        render_full_dashboard({matches[0]["name"]: analyses}, brand_info)
        return EXIT_OK

    run_multi_brand_cycle()
    return EXIT_OK


def _cmd_serve(args):
    from . import web

    return web.main(port=args.port)


def _cmd_reprocess(args):
    try:
        config.require_api_key()
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_USAGE_ERROR

    from . import reprocess

    return reprocess.main()


def _cmd_init_db(args):
    from . import db

    db.main()
    return EXIT_OK


def _cmd_brands(args):
    from .brands import BRANDS

    for b in BRANDS:
        print(f"{b['name']} — {b['category']}")
        for kw in b["keywords"]:
            print(f"    - {kw}")
    return EXIT_OK


_COMMANDS = {
    "scan": _cmd_scan,
    "serve": _cmd_serve,
    "reprocess": _cmd_reprocess,
    "init-db": _cmd_init_db,
    "brands": _cmd_brands,
}


def main(argv=None):
    """Entry point for the `brand-monitor` console script. Returns an exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(config.get_version())
        return EXIT_OK

    # Apply --db before any subcommand touches the database — config.py
    # resolves the DB path at call time, so this must happen before dispatch.
    # --db can be given either before the subcommand (db_global) or after it
    # (db_sub, from the shared `common` parent parser). The subcommand form
    # wins if both are present; fall back to the top-level form otherwise.
    # getattr guards the no-subcommand case (e.g. `--version`), where db_sub
    # was never added to the namespace at all.
    #
    # Resolved with `is not None` (not truthiness) so an explicitly-provided
    # empty string ("") is distinguishable from the flag being absent
    # (None) — see the empty-string check below.
    db_sub = getattr(args, "db_sub", None)
    db_path = db_sub if db_sub is not None else args.db_global
    if db_path == "":
        print("Error: --db requires a non-empty path", file=sys.stderr)
        return EXIT_USAGE_ERROR
    if db_path:
        config.set_db_path(db_path)

    # Load .env for every subcommand, once, before dispatch.
    config.load_env()

    if not args.command:
        parser.print_help()
        return EXIT_USAGE_ERROR

    handler = _COMMANDS[args.command]
    try:
        return handler(args)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return EXIT_INTERRUPTED
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_RUNTIME_ERROR


if __name__ == "__main__":
    sys.exit(main())

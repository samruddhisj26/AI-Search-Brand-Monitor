"""
tests/test_cli.py — smoke tests for brand_monitor/cli.py's main(argv).

main(argv=None) is designed to be called in-process (it returns an int and
only lets argparse's own --help/usage-error paths call sys.exit()), so
these tests drive it directly rather than spawning a subprocess.

Scope: argument parsing and dispatch only — not the scan/serve/reprocess
business logic itself, which lives elsewhere and isn't part of this smoke
pass.
"""

import os

import pytest

from brand_monitor import cli, config


def test_version_flag_returns_zero(capsys):
    code = cli.main(["--version"])
    assert code == 0
    out = capsys.readouterr().out
    assert out.strip()  # prints the version string


def test_no_subcommand_returns_usage_error():
    assert cli.main([]) == 2


def test_brands_subcommand_returns_zero_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert cli.main(["brands"]) == 0


def test_scan_without_api_key_returns_usage_error_and_writes_stderr(monkeypatch, capsys):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    code = cli.main(["scan", "--brand", "Figma"])

    assert code == 2
    captured = capsys.readouterr()
    assert captured.err.strip()  # error text landed on stderr
    assert captured.out == "" or "Error" not in captured.out


def test_help_flag_raises_systemexit_zero():
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--help"])
    assert exc_info.value.code == 0


def test_unknown_subcommand_raises_systemexit_two():
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["not-a-real-subcommand"])
    assert exc_info.value.code == 2


def test_db_flag_before_subcommand_creates_database_at_path(tmp_path):
    db_path = tmp_path / "before.db"

    code = cli.main(["--db", str(db_path), "init-db"])

    assert code == 0
    assert db_path.exists()
    assert config.get_db_path() == os.path.abspath(str(db_path))


def test_db_flag_after_subcommand_creates_database_at_path(tmp_path):
    """
    Per T011 instructions: the CLI is being updated concurrently so --db
    works both before AND after the subcommand. This is the post-subcommand
    form (`init-db --db PATH`). If this is still in flight when the suite
    runs, this test is expected to fail — that failure should be reported
    as "known in-flight work", not treated as a smoke-test regression to
    silently paper over.
    """
    db_path = tmp_path / "after.db"

    code = cli.main(["init-db", "--db", str(db_path)])

    assert code == 0
    assert db_path.exists()
    assert config.get_db_path() == os.path.abspath(str(db_path))


def test_serve_with_missing_db_returns_one_not_systemexit(tmp_path):
    """
    Regression test for T023: web.main() used to call sys.exit(1) when the
    database was missing. SystemExit doesn't inherit from Exception, so it
    escaped cli.main()'s `except Exception` dispatch guard and broke the
    documented contract that main(argv) always RETURNS an int (the one
    documented exception being argparse's own --help/usage-error paths,
    which this isn't). If the regression reappears, this call raises
    SystemExit and pytest reports it as an error rather than the plain
    assertion failure below.
    """
    missing_db = tmp_path / "does-not-exist" / "brand_monitor.db"

    code = cli.main(["serve", "--db", str(missing_db)])

    assert code == 1


def test_db_flag_explicit_empty_string_before_subcommand_is_usage_error():
    """An explicitly-provided empty --db must be a usage error (exit 2),
    not silently fall through to the default database (truthiness bug)."""
    assert cli.main(["--db", "", "init-db"]) == 2


def test_db_flag_explicit_empty_string_after_subcommand_is_usage_error():
    assert cli.main(["init-db", "--db", ""]) == 2


def test_db_flag_absent_still_uses_default_behavior(tmp_path, monkeypatch):
    """Guards against the empty-string fix over-triggering when --db is
    simply never passed at all."""
    monkeypatch.chdir(tmp_path)
    assert cli.main(["init-db"]) == 0


def test_db_flag_with_nested_missing_directory_creates_it(tmp_path):
    """Regression test for T025: --db pointed at a path whose parent
    directories don't exist yet must have those directories created
    automatically, not fail with a raw sqlite3 "unable to open database
    file" error."""
    db_path = tmp_path / "nested" / "sub" / "x.db"

    code = cli.main(["--db", str(db_path), "init-db"])

    assert code == 0
    assert db_path.exists()

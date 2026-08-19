"""
brand_monitor/config.py — Single source of truth for runtime configuration.

Everything here resolves at CALL time, never at import time. This is what
lets a `--db` flag, an `.env` file, or a plain exported env var actually
take effect when this package is installed and run as a CLI — instead of
being silently ignored because values were frozen the moment a module was
first imported.
"""

import os

from . import __version__

APP_NAME = "AI Search Brand Monitor"
PROJECT_URL = "https://github.com/samruddhisj26/AI-Search-Brand-Monitor"

OPENROUTER_API_KEY_ENV = "OPENROUTER_API_KEY"
ANALYSIS_MODEL_ENV = "ANALYSIS_MODEL"
DB_PATH_ENV = "BRAND_MONITOR_DB"
OUTPUT_DIR_ENV = "BRAND_MONITOR_OUTPUT"

DEFAULT_ANALYSIS_MODEL = "openai/gpt-4o-mini"
DEFAULT_DB_FILENAME = "brand_monitor.db"
DEFAULT_OUTPUT_DIRNAME = "output"

_db_path_override = None
_output_dir_override = None
_env_loaded = False


def load_env():
    """
    Load a .env file if python-dotenv is installed, searching upward from
    the current working directory so it works from a subdirectory too.

    Safe no-op if python-dotenv isn't installed. Never overrides variables
    already present in the real environment — plain `export`ed vars always
    win. Idempotent: safe to call more than once.
    """
    global _env_loaded
    if _env_loaded:
        return
    try:
        from dotenv import find_dotenv, load_dotenv
    except ImportError:
        _env_loaded = True
        return
    dotenv_path = find_dotenv(usecwd=True)
    if dotenv_path:
        load_dotenv(dotenv_path, override=False)
    _env_loaded = True


def get_api_key():
    """Return OPENROUTER_API_KEY from the environment at call time, or ''."""
    return os.environ.get(OPENROUTER_API_KEY_ENV, "")


def require_api_key():
    """
    Return the OpenRouter API key, or raise RuntimeError with a clear
    message pointing at .env.example if it isn't set.
    """
    key = get_api_key()
    if not key:
        raise RuntimeError(
            f"{OPENROUTER_API_KEY_ENV} is not set. "
            f"Copy .env.example to .env and add your key, or "
            f"export {OPENROUTER_API_KEY_ENV}=... before running."
        )
    return key


def get_analysis_model():
    """Return ANALYSIS_MODEL from the environment at call time."""
    return os.environ.get(ANALYSIS_MODEL_ENV, DEFAULT_ANALYSIS_MODEL)


def get_headers(title=None):
    """Build the OpenRouter request headers dict at call time."""
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {get_api_key()}",
        "HTTP-Referer": PROJECT_URL,
        "X-Title": title or APP_NAME,
    }


def set_db_path(path):
    """Set (or, with None, clear) an explicit DB path override."""
    global _db_path_override
    _db_path_override = path


def get_db_path():
    """
    Resolve the database path, highest precedence first:
      1. an explicit override set via set_db_path()
      2. $BRAND_MONITOR_DB
      3. ./brand_monitor.db relative to the current working directory
    Always returns an absolute path.
    """
    if _db_path_override:
        return os.path.abspath(_db_path_override)
    env_path = os.environ.get(DB_PATH_ENV)
    if env_path:
        return os.path.abspath(env_path)
    return os.path.abspath(DEFAULT_DB_FILENAME)


def ensure_db_dir():
    """
    Ensure the parent directory of the resolved database path exists,
    creating any missing intermediate directories (mirrors the
    os.makedirs(..., exist_ok=True) pattern already used for the output
    directory in runner.py / reprocess.py).

    No-op when the resolved path has no directory component (a bare
    filename like the default "brand_monitor.db", relative to the CWD) or
    when the directory already exists. Raises RuntimeError naming the
    path if creation genuinely fails (permissions, a file occupying the
    directory's name, etc.) so callers get a clear message instead of a
    raw traceback or a confusing sqlite3 "unable to open database file".
    """
    parent = os.path.dirname(get_db_path())
    if not parent:
        return
    try:
        os.makedirs(parent, exist_ok=True)
    except OSError as e:
        raise RuntimeError(
            f"Unable to create directory for database path {parent!r}: {e}"
        ) from e


def set_output_dir(path):
    """Set (or, with None, clear) an explicit output directory override."""
    global _output_dir_override
    _output_dir_override = path


def get_output_dir():
    """
    Resolve the output directory, highest precedence first:
      1. an explicit override set via set_output_dir()
      2. $BRAND_MONITOR_OUTPUT
      3. ./output relative to the current working directory
    Always returns an absolute path. Does not create the directory.
    """
    if _output_dir_override:
        return os.path.abspath(_output_dir_override)
    env_path = os.environ.get(OUTPUT_DIR_ENV)
    if env_path:
        return os.path.abspath(env_path)
    return os.path.abspath(DEFAULT_OUTPUT_DIRNAME)


def get_footer():
    """Single source for the report footer text."""
    return f"{APP_NAME} · {PROJECT_URL}"


def get_version():
    """Return the package version."""
    return __version__

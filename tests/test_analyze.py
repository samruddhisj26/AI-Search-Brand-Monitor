"""
tests/test_analyze.py — smoke tests for brand_monitor/analyze.py's
analyze_response(), the highest-value target: it makes a network call then
parses the model's (sometimes messy) JSON reply.

We never hit the network. `urllib.request.urlopen` is patched at the
IMPORT SITE USED BY THE MODULE UNDER TEST — `brand_monitor.analyze` —
not `brand_monitor.query`, which imports its own separate reference to
`urllib.request` and would silently leave a real urlopen in place if we
patched the wrong one. Each patch site is proven to have taken effect by
asserting the fake's call count.

Scope: JSON-response parsing only. Not testing the rich rendering, the web
dashboard, or the scoring heuristics elsewhere in the app.
"""

import io
import json
import urllib.error

import pytest

from brand_monitor import analyze


class _FakeResponse:
    """Minimal stand-in for the object returned by urlopen()'s context
    manager: needs .read() and to work with `with ... as resp:`."""

    def __init__(self, body: dict):
        self._body = json.dumps(body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._body


def _openrouter_payload(content: str) -> dict:
    """Wrap `content` (the model's raw reply string) in the OpenRouter
    chat-completions response envelope that analyze.py expects."""
    return {"choices": [{"message": {"content": content}}]}


@pytest.fixture
def fake_urlopen(monkeypatch):
    """
    Patches urllib.request.urlopen as seen by brand_monitor.analyze
    specifically (not brand_monitor.query, which has its own independent
    `import urllib.request`). Records calls so tests can prove the patch
    took effect and that no real network call happened.
    """
    calls = []

    def _make(content_or_exc):
        def _fake(req, timeout=None):
            calls.append(req)
            if isinstance(content_or_exc, BaseException):
                raise content_or_exc
            return _FakeResponse(_openrouter_payload(content_or_exc))

        monkeypatch.setattr("brand_monitor.analyze.urllib.request.urlopen", _fake)
        return calls

    return _make


EXPECTED_DICT = {
    "brand_mentioned": True,
    "sentiment": "positive",
    "accuracy": "accurate",
    "competitors": ["Sketch", "Adobe XD"],
    "visibility_score": 75,
    "summary": "Figma was recommended as a top design tool.",
}


def test_bare_json_no_markdown_fence(fake_urlopen, junk_api_key):
    calls = fake_urlopen(json.dumps(EXPECTED_DICT))

    result = analyze.analyze_response("Figma", "chatgpt", "best design tool", "some AI reply")

    assert result == EXPECTED_DICT
    assert len(calls) == 1  # proves the patch took effect / real network never touched


def test_json_wrapped_in_json_fence(fake_urlopen, junk_api_key):
    content = "```json\n" + json.dumps(EXPECTED_DICT) + "\n```"
    fake_urlopen(content)

    result = analyze.analyze_response("Figma", "chatgpt", "best design tool", "some AI reply")

    assert result == EXPECTED_DICT


def test_json_wrapped_in_plain_fence(fake_urlopen, junk_api_key):
    content = "```\n" + json.dumps(EXPECTED_DICT) + "\n```"
    fake_urlopen(content)

    result = analyze.analyze_response("Figma", "chatgpt", "best design tool", "some AI reply")

    assert result == EXPECTED_DICT


def test_json_with_surrounding_whitespace_inside_fence(fake_urlopen, junk_api_key):
    content = "```json\n\n   \n" + json.dumps(EXPECTED_DICT) + "\n\n  \n```"
    fake_urlopen(content)

    result = analyze.analyze_response("Figma", "chatgpt", "best design tool", "some AI reply")

    assert result == EXPECTED_DICT


def test_malformed_json_returns_documented_fallback_without_raising(fake_urlopen, junk_api_key):
    fake_urlopen("{not valid json at all")

    result = analyze.analyze_response("Figma", "chatgpt", "best design tool", "some AI reply")

    assert result["brand_mentioned"] is False
    assert result["sentiment"] is None
    assert result["accuracy"] is None
    assert result["competitors"] == []
    assert result["visibility_score"] == 0
    assert "Could not parse analysis output" in result["summary"]


def test_empty_response_text_returns_fallback_without_network_call(fake_urlopen, junk_api_key):
    calls = fake_urlopen(json.dumps(EXPECTED_DICT))  # would succeed if ever called

    result = analyze.analyze_response("Figma", "chatgpt", "best design tool", "")

    assert result == {
        "brand_mentioned": False,
        "sentiment": None,
        "accuracy": None,
        "competitors": [],
        "visibility_score": 0,
        "summary": "No response to analyze.",
    }
    assert calls == []  # no network call was made for a falsy response_text


def test_missing_keys_in_valid_json_get_documented_defaults(fake_urlopen, junk_api_key):
    # Only `sentiment` and `summary` present — everything else is missing.
    partial = {"sentiment": "neutral", "summary": "Brief mention."}
    fake_urlopen(json.dumps(partial))

    result = analyze.analyze_response("Figma", "chatgpt", "best design tool", "some AI reply")

    assert result["brand_mentioned"] is False
    assert result["competitors"] == []
    assert result["visibility_score"] == 0
    assert result["sentiment"] == "neutral"
    assert result["summary"] == "Brief mention."


def test_http_error_returns_fallback_with_error_in_summary_and_does_not_raise(
    fake_urlopen, junk_api_key
):
    http_err = urllib.error.HTTPError(
        "https://openrouter.ai/api/v1/chat/completions",
        500,
        "Internal Server Error",
        {},
        io.BytesIO(b""),
    )
    fake_urlopen(http_err)

    result = analyze.analyze_response("Figma", "chatgpt", "best design tool", "some AI reply")

    assert result["brand_mentioned"] is False
    assert result["sentiment"] is None
    assert result["accuracy"] is None
    assert result["competitors"] == []
    assert result["visibility_score"] == 0
    assert "Analysis failed" in result["summary"]
    assert "500" in result["summary"]


def test_pins_known_defect_unfenced_prose_around_json_is_indistinguishable_from_not_mentioned(
    fake_urlopen, junk_api_key
):
    """
    KNOWN PRE-EXISTING BUG (deferred, not fixed here): when the model
    returns free-form prose *around* a JSON blob with no code fence at all
    (e.g. "Sure, here's the analysis: {...} Let me know if you need more."),
    analyze_response()'s parser has no fallback extraction step — it only
    strips ```json/``` fences, so `json.loads(raw)` fails on the leading
    prose and this falls into the generic JSONDecodeError handler. The
    result is a *fallback* dict (visibility_score 0, brand_mentioned False)
    that is bit-for-bit indistinguishable from a genuine "brand not
    mentioned" verdict, even though the model's JSON payload above clearly
    says the brand WAS mentioned prominently.

    This test PINS the current (buggy) behavior so a future fix is a
    deliberate, visible change rather than a silent regression. Do not
    "fix" this test by changing analyze.py — file/track the real fix
    separately (deferred bug).
    """
    embedded = json.dumps(EXPECTED_DICT)  # brand_mentioned True, visibility_score 75
    prose_wrapped = f"Sure, here's the analysis:\n{embedded}\nLet me know if you need anything else!"
    fake_urlopen(prose_wrapped)

    result = analyze.analyze_response("Figma", "chatgpt", "best design tool", "some AI reply")

    # Pinned buggy behavior: falls back to the "not mentioned" shape despite
    # the embedded JSON actually saying brand_mentioned=True.
    assert result["brand_mentioned"] is False
    assert result["visibility_score"] == 0
    assert "Could not parse analysis output" in result["summary"]

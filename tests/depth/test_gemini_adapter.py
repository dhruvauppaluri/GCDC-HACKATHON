"""Contract checks for the optional Gemini structured-output transport."""

import httpx
import pytest

from backend.depth import gemini_adapter
from backend.web import gemini_client


def _response(body, status=200):
    return httpx.Response(status, json=body, request=httpx.Request("POST", "https://generativelanguage.googleapis.com"))


def test_depth_gemini_adapter_sends_schema_and_parses_json(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("DEPTH_GEMINI_MODEL", "gemini-test")
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return _response({"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": '{"dimensions": {"verification": null}}'}]}}]})

    monkeypatch.setattr(gemini_client.httpx, "post", fake_post)
    result = gemini_adapter.gemini_json("Assess", {"evidence": []}, answer_only=True, dimensions=("verification",))
    assert result == {"dimensions": {"verification": None}}
    url, kwargs = calls[0]
    assert url.endswith("/models/gemini-test:generateContent")
    assert kwargs["headers"] == {"x-goog-api-key": "test-key"}
    assert kwargs["json"]["generationConfig"]["responseMimeType"] == "application/json"
    assert kwargs["json"]["generationConfig"]["responseJsonSchema"]["properties"]["dimensions"]["required"] == ["verification"]


def test_gemini_requires_key_before_network(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        gemini_client.generate_json("", {}, {"type": "object"})


def test_gemini_rejects_truncated_or_blocked_response(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(gemini_client.httpx, "post", lambda *_args, **_kwargs: _response({"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "{}"}]}}]}))
    with pytest.raises(RuntimeError, match="did not finish normally"):
        gemini_client.generate_json("", {}, {"type": "object"})
    monkeypatch.setattr(gemini_client.httpx, "post", lambda *_args, **_kwargs: _response({"promptFeedback": {"blockReason": "SAFETY"}}))
    with pytest.raises(RuntimeError, match="no valid JSON"):
        gemini_client.generate_json("", {}, {"type": "object"})


def test_gemini_quota_error_has_no_response_body(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(gemini_client.httpx, "post", lambda *_args, **_kwargs: _response({"error": "private content"}, 429))
    with pytest.raises(RuntimeError, match="quota was exceeded") as exc:
        gemini_client.generate_json("", {}, {"type": "object"})
    assert "private content" not in str(exc.value)

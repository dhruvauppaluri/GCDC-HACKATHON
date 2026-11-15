"""Contract checks for the optional Gemini structured-output transport."""

import httpx
import pytest

from backend.depth import gemini_adapter
from backend.web import gemini_client


@pytest.fixture(autouse=True)
def isolated_key_pool(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY_2", raising=False)
    with gemini_client._KEY_LOCK:
        gemini_client._NEXT_KEY = 0
        gemini_client._COOLDOWN_UNTIL.clear()


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


def test_gemini_payment_error_explains_billing_without_echoing_body(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(gemini_client.httpx, "post", lambda *_args, **_kwargs: _response({"error": "private content"}, 402))
    with pytest.raises(RuntimeError, match="prepay credits are depleted") as exc:
        gemini_client.generate_json("", {}, {"type": "object"})
    assert "private content" not in str(exc.value)


def test_gemini_retries_transient_server_failure(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(gemini_client.time, "sleep", lambda _: None)
    attempts = []
    def fake_post(*_args, **_kwargs):
        attempts.append(1)
        return _response({"error": "temporary"}, 503) if len(attempts) < 3 else _response({
            "candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "{}"}]}}]})
    monkeypatch.setattr(gemini_client.httpx, "post", fake_post)
    assert gemini_client.generate_json("", {}, {"type": "object"}) == {}
    assert len(attempts) == 3


def test_two_keys_are_balanced_across_calls(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "first-key")
    monkeypatch.setenv("GEMINI_API_KEY_2", "second-key")
    sent = []
    def fake_post(_url, **kwargs):
        sent.append(kwargs["headers"]["x-goog-api-key"])
        return _response({"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "{}"}]}}]})
    monkeypatch.setattr(gemini_client.httpx, "post", fake_post)
    for _ in range(4):
        assert gemini_client.generate_json("", {}, {"type": "object"}) == {}
    assert sent == ["first-key", "second-key", "first-key", "second-key"]


def test_quota_on_one_key_falls_back_to_other_and_cools_down(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "first-key")
    monkeypatch.setenv("GEMINI_API_KEY_2", "second-key")
    sent = []
    def fake_post(_url, **kwargs):
        key = kwargs["headers"]["x-goog-api-key"]
        sent.append(key)
        return (_response({"error": {"status": "RESOURCE_EXHAUSTED", "message": "quota_exceeded"}}, 429)
                if key == "first-key" else
                _response({"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "{}"}]}}]}))
    monkeypatch.setattr(gemini_client.httpx, "post", fake_post)
    assert gemini_client.generate_json("", {}, {"type": "object"}) == {}
    assert gemini_client.generate_json("", {}, {"type": "object"}) == {}
    assert sent == ["first-key", "second-key", "second-key"]


def test_secondary_key_works_without_primary(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY_2", "second-key")
    monkeypatch.setattr(gemini_client.httpx, "post", lambda _url, **kwargs: _response({
        "candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "{}"}]}}]}))
    assert gemini_client.gemini_keys_available()
    assert gemini_client.generate_json("", {}, {"type": "object"}) == {}


def test_repeated_service_error_falls_back_to_secondary(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "first-key")
    monkeypatch.setenv("GEMINI_API_KEY_2", "second-key")
    monkeypatch.setattr(gemini_client.time, "sleep", lambda _: None)
    sent = []
    def fake_post(_url, **kwargs):
        key = kwargs["headers"]["x-goog-api-key"]
        sent.append(key)
        return (_response({"error": "temporary"}, 503) if key == "first-key" else
                _response({"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "{}"}]}}]}))
    monkeypatch.setattr(gemini_client.httpx, "post", fake_post)
    assert gemini_client.generate_json("", {}, {"type": "object"}) == {}
    assert sent == ["first-key", "first-key", "first-key", "second-key"]

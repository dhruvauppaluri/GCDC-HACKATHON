import pytest


@pytest.fixture(autouse=True)
def no_persistent_model_caches(monkeypatch, tmp_path):
    """Model-call caches are for production determinism; tests must never share them."""
    monkeypatch.setenv("DEPTH_EVAL_CACHE", "0")
    monkeypatch.setenv("MATCH_CACHE_PATH", str(tmp_path / "match-cache.sqlite3"))
    monkeypatch.setenv("GEMINI_RPM", "0")

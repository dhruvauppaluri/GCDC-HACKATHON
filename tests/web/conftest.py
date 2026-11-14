import pytest


@pytest.fixture(autouse=True)
def disable_external_feed_in_web_tests(monkeypatch):
    monkeypatch.setenv("SIMPLIFY_FEED_ENABLED", "0")

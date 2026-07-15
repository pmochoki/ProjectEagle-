from ai.client import DEFAULT_MODEL, get_model


def test_default_model_is_current(monkeypatch):
    monkeypatch.delenv("CLAUDE_MODEL", raising=False)
    assert get_model() == DEFAULT_MODEL
    assert get_model() != "claude-sonnet-4-20250514"


def test_retired_model_is_remapped(monkeypatch):
    monkeypatch.setenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
    assert get_model() == "claude-sonnet-4-6"

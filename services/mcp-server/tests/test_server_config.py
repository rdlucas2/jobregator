"""Configuration must fail at startup, not per listing.

A missing credential that surfaces as a per-message enrichment failure looks
exactly like a model problem in the logs and quietly degrades every listing.
"""

import pytest

import src.server as server


@pytest.fixture(autouse=True)
def reset_module_state(monkeypatch):
    monkeypatch.setattr(server, "_typesafe_client", None)
    monkeypatch.setattr(server, "_typed_provider", None)
    yield


def test_jev_without_an_api_key_fails_with_an_actionable_message(monkeypatch):
    monkeypatch.setattr(server, "TYPED_PROVIDER", "jev")
    monkeypatch.setattr(server, "TYPESAFE_API_KEY", "")

    with pytest.raises(RuntimeError, match="TYPESAFE_API_KEY"):
        server._get_typesafe_client()


def test_the_default_typed_provider_is_jev():
    import importlib
    monkeypatch_env = {}
    reloaded = importlib.reload(server)
    assert reloaded.TYPED_PROVIDER == "jev"


def test_jev_model_is_pinned_by_default():
    assert server.JEV_MODEL == "jev-1.13.0"


def test_claude_remains_selectable_without_a_typesafe_key(monkeypatch):
    """Reverting must need no code change and no TypeSafe credential."""
    monkeypatch.setattr(server, "TYPED_PROVIDER", "claude")
    monkeypatch.setattr(server, "TYPESAFE_API_KEY", "")
    monkeypatch.setattr(server, "ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(server, "_llm", object())

    provider = server._get_typed_provider()

    assert provider is not None

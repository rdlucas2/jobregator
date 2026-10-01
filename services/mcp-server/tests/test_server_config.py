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


def test_the_default_typed_provider_is_claude():
    """Claude is the default while TypeSafe signups are closed. The jev path
    stays implemented and tested; only the default moved."""
    import importlib

    reloaded = importlib.reload(server)
    assert reloaded.TYPED_PROVIDER == "claude"


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


def test_laya_without_a_base_url_fails_with_an_actionable_message(monkeypatch):
    monkeypatch.setattr(server, "TYPED_PROVIDER", "laya")
    monkeypatch.setattr(server, "LAYA_BASE_URL", "")

    with pytest.raises(RuntimeError, match="LAYA_BASE_URL"):
        server._get_typed_provider()


class RecordingClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


@pytest.fixture
def recording_client(monkeypatch):
    import typesafe_sdk

    monkeypatch.setattr(typesafe_sdk, "AsyncTypeSafeClient", RecordingClient)


def test_laya_client_targets_the_configured_server(monkeypatch, recording_client):
    monkeypatch.setattr(server, "LAYA_BASE_URL", "http://host.docker.internal:8000")
    monkeypatch.setattr(server, "LAYA_API_KEY", "")

    client = server._get_laya_client()

    assert client.kwargs["base_url"] == "http://host.docker.internal:8000"
    # The SDK refuses an empty key even though laya-serve auth is optional.
    assert client.kwargs["api_key"]


def test_laya_client_sends_the_configured_key_when_there_is_one(
    monkeypatch, recording_client
):
    monkeypatch.setattr(server, "LAYA_BASE_URL", "http://laya:8000")
    monkeypatch.setattr(server, "LAYA_API_KEY", "secret")

    assert server._get_laya_client().kwargs["api_key"] == "secret"


@pytest.mark.asyncio
async def test_laya_selected_end_to_end_needs_no_anthropic_or_typesafe_key(
    monkeypatch,
):
    """Laya runs locally: no cloud credential of any kind is required."""
    from tests.test_jev_provider import LISTING, PROFILE, StubClient

    monkeypatch.setattr(server, "TYPED_PROVIDER", "laya")
    monkeypatch.setattr(server, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(server, "TYPESAFE_API_KEY", "")
    monkeypatch.setattr(server, "LAYA_MODEL", "laya-english")
    monkeypatch.setattr(server, "_typesafe_client", StubClient())
    monkeypatch.setattr(server, "LAYA_BASE_URL", "http://laya:8000")

    decisions = await server._get_typed_provider().decide(LISTING, PROFILE)

    assert decisions.provider == "laya"
    assert server._typesafe_client.model_arg == "laya-english"

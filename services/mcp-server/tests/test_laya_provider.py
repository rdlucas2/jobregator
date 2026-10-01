"""Laya serves Jev's /v1/systemone wire protocol, so the laya provider is the
jev question set and answer mapping pointed at a different server. These tests
pin what differs: selection by name, the label stored with each decision, and
the model Laya is asked for.
"""

import pytest

from src.providers.factory import build_typed_provider
from tests.test_jev_provider import LISTING, PROFILE, StubClient


@pytest.mark.asyncio
async def test_laya_decisions_are_labelled_with_the_laya_provider():
    client = StubClient()
    provider = build_typed_provider("laya", typesafe_client=client)

    decisions = await provider.decide(LISTING, PROFILE)

    assert client.calls == 1
    assert decisions.provider == "laya"
    assert decisions.experience_level == "senior"


@pytest.mark.asyncio
async def test_laya_is_asked_for_the_configured_model():
    client = StubClient()
    provider = build_typed_provider(
        "laya", typesafe_client=client, laya_model="laya-english"
    )

    await provider.decide(LISTING, PROFILE)

    assert client.model_arg == "laya-english"


@pytest.mark.asyncio
async def test_laya_is_asked_for_its_own_model_by_default_not_a_jev_one():
    client = StubClient()
    provider = build_typed_provider("laya", typesafe_client=client)

    await provider.decide(LISTING, PROFILE)

    assert client.model_arg == "laya"


def test_asking_for_laya_without_a_client_fails_loudly():
    with pytest.raises(ValueError, match="typesafe_client"):
        build_typed_provider("laya")

"""The worker calls analyze_job and score_job_fit back-to-back for the same
listing, and both need the typed decisions. Without memoization that is two
model calls where the previous design made one, turning a refactor into a cost
regression."""

import pytest

from src.providers.base import Decisions
from src.providers.cache import CachingTypedDecisions


class CountingProvider:
    def __init__(self):
        self.calls = 0

    async def decide(self, listing: dict, profile: str) -> Decisions:
        self.calls += 1
        return Decisions(
            fit_score=0.8,
            experience_level="senior",
            remote_policy="remote",
            job_type="full_time",
            requires_office_presence=0.01,
            requires_relocation=0.01,
            is_contract_or_freelance=0.01,
            provider="counting",
            model="counting-1",
        )


LISTING = {"title": "Senior DevOps Engineer", "company": "Acme", "description": "Remote."}


@pytest.mark.asyncio
async def test_repeated_decide_for_the_same_listing_hits_the_model_once():
    inner = CountingProvider()
    provider = CachingTypedDecisions(inner)

    first = await provider.decide(LISTING, "profile")
    second = await provider.decide(LISTING, "profile")

    assert inner.calls == 1
    assert first == second


@pytest.mark.asyncio
async def test_a_different_listing_is_not_served_from_cache():
    inner = CountingProvider()
    provider = CachingTypedDecisions(inner)

    await provider.decide(LISTING, "profile")
    await provider.decide({**LISTING, "title": "Platform Engineer"}, "profile")

    assert inner.calls == 2


@pytest.mark.asyncio
async def test_a_changed_profile_invalidates_the_cache():
    """The profile is part of the judgment, not just the listing."""
    inner = CountingProvider()
    provider = CachingTypedDecisions(inner)

    await provider.decide(LISTING, "profile A")
    await provider.decide(LISTING, "profile B")

    assert inner.calls == 2


@pytest.mark.asyncio
async def test_cache_evicts_so_a_long_running_server_does_not_grow_unbounded():
    inner = CountingProvider()
    provider = CachingTypedDecisions(inner, maxsize=2)

    await provider.decide({**LISTING, "title": "A"}, "profile")
    await provider.decide({**LISTING, "title": "B"}, "profile")
    await provider.decide({**LISTING, "title": "C"}, "profile")
    await provider.decide({**LISTING, "title": "A"}, "profile")  # evicted

    assert inner.calls == 4


@pytest.mark.asyncio
async def test_the_two_mcp_tool_shapes_share_one_cache_entry():
    """Regression: analyze_job passes `location`, score_job_fit does not.

    If the cache key includes a field only one caller supplies, the two tools
    never share an entry and the memoization silently does nothing — restoring
    the extra model call it exists to remove.
    """
    inner = CountingProvider()
    provider = CachingTypedDecisions(inner)

    # as analyze_job builds it
    await provider.decide({**LISTING, "location": "Remote, USA"}, "profile")
    # as score_job_fit builds it
    await provider.decide(LISTING, "profile")

    assert inner.calls == 1

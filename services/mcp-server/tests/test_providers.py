import pytest

from src.providers.base import Decisions
from src.tools import score_fit


class FakeTypedProvider:
    """Stand-in for a TypedDecisionProvider at the model boundary."""

    def __init__(self, decisions: Decisions):
        self.decisions = decisions
        self.calls = []

    async def decide(self, listing: dict, profile: str) -> Decisions:
        self.calls.append((listing, profile))
        return self.decisions


def make_decisions(**overrides) -> Decisions:
    defaults = dict(
        fit_score=0.8,
        experience_level="senior",
        remote_policy="remote",
        job_type="full_time",
        requires_office_presence=0.02,
        requires_relocation=0.01,
        is_contract_or_freelance=0.03,
        confidence={},
        provider="fake",
        model="fake-1",
    )
    defaults.update(overrides)
    return Decisions(**defaults)


@pytest.mark.asyncio
async def test_score_fit_returns_score_from_typed_provider():
    provider = FakeTypedProvider(make_decisions(fit_score=0.82))

    result = await score_fit(
        {"title": "Senior DevOps Engineer", "company": "Acme", "description": "Fully remote."},
        profile="Senior DevOps Engineer, 15+ years.",
        typed_provider=provider,
    )

    assert result["score"] == 0.82


@pytest.mark.asyncio
async def test_office_presence_caps_the_fit_score():
    """A strong-on-paper role that requires office attendance is capped.

    This policy used to live inside the scoring prompt ("cap at 0.3 max"),
    where it could not be tested and could not apply to a provider that takes
    no prose instructions.
    """
    provider = FakeTypedProvider(
        make_decisions(fit_score=0.95, requires_office_presence=0.91)
    )

    result = await score_fit({"title": "Senior DevOps Engineer"}, "profile", provider)

    assert result["score"] == 0.3


@pytest.mark.asyncio
async def test_score_passes_through_when_office_presence_is_below_threshold():
    provider = FakeTypedProvider(
        make_decisions(fit_score=0.95, requires_office_presence=0.5)
    )

    result = await score_fit({"title": "Senior DevOps Engineer"}, "profile", provider)

    assert result["score"] == 0.95


@pytest.mark.asyncio
async def test_cap_never_raises_a_weak_score():
    """The cap is a ceiling, not an assignment."""
    provider = FakeTypedProvider(
        make_decisions(fit_score=0.05, requires_office_presence=0.99)
    )

    result = await score_fit({"title": "Junior Helpdesk"}, "profile", provider)

    assert result["score"] == 0.05


@pytest.mark.asyncio
async def test_reasoning_explains_a_capped_score_with_its_probabilities():
    """Jev returns no prose, so reasoning is synthesized from the decisions.

    Buying a sentence from Claude to narrate a Jev score would spend more than
    the decision itself costs.
    """
    provider = FakeTypedProvider(
        make_decisions(fit_score=0.95, requires_office_presence=0.91)
    )

    result = await score_fit({"title": "Senior DevOps Engineer"}, "profile", provider)

    assert "0.30" in result["reasoning"]
    assert "0.95" in result["reasoning"]
    assert "0.91" in result["reasoning"]
    assert "office" in result["reasoning"].lower()


@pytest.mark.asyncio
async def test_reasoning_for_an_uncapped_score_does_not_claim_a_cap():
    provider = FakeTypedProvider(
        make_decisions(fit_score=0.88, requires_office_presence=0.03)
    )

    result = await score_fit({"title": "Senior DevOps Engineer"}, "profile", provider)

    assert "0.88" in result["reasoning"]
    assert "cap" not in result["reasoning"].lower()


@pytest.mark.asyncio
async def test_score_fit_records_which_provider_produced_the_score():
    provider = FakeTypedProvider(make_decisions(provider="claude", model="claude-x"))

    result = await score_fit({"title": "Senior DevOps Engineer"}, "profile", provider)

    assert result["provider"] == "claude"
    assert result["model"] == "claude-x"


class FakeTextProvider:
    def __init__(self, enrichment):
        self.enrichment = enrichment
        self.calls = 0

    async def enrich(self, listing: dict):
        self.calls += 1
        return self.enrichment


@pytest.mark.asyncio
async def test_analyze_job_listing_merges_both_providers():
    """The MCP tool contract is frozen: these keys must keep appearing,
    even though they now come from two different providers."""
    from src.providers.base import TextEnrichment
    from src.tools import analyze_job_listing

    typed = FakeTypedProvider(
        make_decisions(experience_level="senior", remote_policy="hybrid", job_type="full_time")
    )
    text = FakeTextProvider(
        TextEnrichment(
            skills=["Kubernetes", "Terraform"],
            tech_stack=["AWS", "Docker"],
            remote_flags=["3 days in office required"],
            summary="Senior platform role.",
            provider="claude",
            model="claude-test-1",
        )
    )

    result = await analyze_job_listing(
        {"title": "Senior DevOps Engineer"},
        profile="profile",
        typed_provider=typed,
        text_provider=text,
    )

    assert result["experience_level"] == "senior"
    assert result["remote_policy"] == "hybrid"
    assert result["job_type"] == "full_time"
    assert result["skills"] == ["Kubernetes", "Terraform"]
    assert result["tech_stack"] == ["AWS", "Docker"]
    assert result["remote_flags"] == ["3 days in office required"]
    assert result["summary"] == "Senior platform role."
    assert result["provider"] == "fake"

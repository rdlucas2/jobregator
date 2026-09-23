import json
import pytest

from src.providers.base import EnrichmentError
from src.providers.claude import ClaudeTypedDecisions


class FakeLLM:
    """Stand-in for the Anthropic client at the system boundary."""

    def __init__(self, response_text: str = "", raises: Exception | None = None):
        self.response_text = response_text
        self.raises = raises
        self.model = "claude-test-1"
        self.last_prompt = None

    async def complete(self, prompt: str) -> str:
        self.last_prompt = prompt
        if self.raises:
            raise self.raises
        return self.response_text


TYPED_RESPONSE = json.dumps({
    "fit_score": 0.82,
    "experience_level": "senior",
    "remote_policy": "remote",
    "job_type": "full_time",
    "requires_office_presence": 0.05,
    "requires_relocation": 0.02,
    "is_contract_or_freelance": 0.01,
})

LISTING = {
    "title": "Senior DevOps Engineer",
    "company": "Acme Corp",
    "location": "Remote, USA",
    "description": "Fully remote platform engineering role. Terraform, Kubernetes.",
}


@pytest.mark.asyncio
async def test_maps_a_claude_response_onto_decisions():
    llm = FakeLLM(TYPED_RESPONSE)
    provider = ClaudeTypedDecisions(llm)

    decisions = await provider.decide(LISTING, profile="Senior DevOps Engineer.")

    assert decisions.fit_score == 0.82
    assert decisions.experience_level == "senior"
    assert decisions.remote_policy == "remote"
    assert decisions.job_type == "full_time"
    assert decisions.requires_office_presence == 0.05
    assert decisions.provider == "claude"
    assert decisions.model == "claude-test-1"
    # The listing and profile must actually reach the model.
    assert "Senior DevOps Engineer" in llm.last_prompt
    assert "Acme Corp" in llm.last_prompt


@pytest.mark.asyncio
async def test_unparseable_response_raises_instead_of_scoring_zero():
    """Regression: a parse failure used to return {"score": 0.0}.

    That made a perfect match indistinguishable from a rejected one, silently
    suppressing its Discord notification with only a "score: 0.00" log line.
    """
    provider = ClaudeTypedDecisions(FakeLLM("Sure! Here's the JSON: {oops"))

    with pytest.raises(EnrichmentError):
        await provider.decide(LISTING, profile="Senior DevOps Engineer.")


@pytest.mark.asyncio
async def test_missing_field_raises_and_names_the_field():
    incomplete = json.dumps({"fit_score": 0.8, "experience_level": "senior"})
    provider = ClaudeTypedDecisions(FakeLLM(incomplete))

    with pytest.raises(EnrichmentError, match="remote_policy"):
        await provider.decide(LISTING, profile="Senior DevOps Engineer.")


@pytest.mark.asyncio
async def test_transport_failure_propagates_as_enrichment_error():
    """Regression: the old except block referenced an unbound `response`,
    so a transport failure raised NameError from inside the handler."""
    provider = ClaudeTypedDecisions(FakeLLM(raises=ConnectionError("boom")))

    with pytest.raises(EnrichmentError, match="boom"):
        await provider.decide(LISTING, profile="Senior DevOps Engineer.")


@pytest.mark.asyncio
async def test_out_of_range_scores_are_clamped():
    wild = json.loads(TYPED_RESPONSE)
    wild["fit_score"] = 4.2
    wild["requires_office_presence"] = -1.0
    provider = ClaudeTypedDecisions(FakeLLM(json.dumps(wild)))

    decisions = await provider.decide(LISTING, profile="Senior DevOps Engineer.")

    assert decisions.fit_score == 1.0
    assert decisions.requires_office_presence == 0.0


TEXT_RESPONSE = json.dumps({
    "skills": ["Kubernetes", "Terraform", "CI/CD"],
    "tech_stack": ["AWS", "Docker", "GitHub Actions"],
    "remote_flags": ["3 days in office required"],
    "summary": "Senior platform role focused on cloud infrastructure.",
})


@pytest.mark.asyncio
async def test_text_enrichment_returns_the_open_ended_fields():
    from src.providers.claude import ClaudeTextEnrichment

    llm = FakeLLM(TEXT_RESPONSE)
    provider = ClaudeTextEnrichment(llm)

    enrichment = await provider.enrich(LISTING)

    assert enrichment.skills == ["Kubernetes", "Terraform", "CI/CD"]
    assert enrichment.tech_stack == ["AWS", "Docker", "GitHub Actions"]
    assert enrichment.remote_flags == ["3 days in office required"]
    assert "platform" in enrichment.summary
    assert enrichment.provider == "claude"
    assert "Senior DevOps Engineer" in llm.last_prompt


@pytest.mark.asyncio
async def test_text_enrichment_transport_failure_raises():
    from src.providers.claude import ClaudeTextEnrichment

    provider = ClaudeTextEnrichment(FakeLLM(raises=ConnectionError("boom")))

    with pytest.raises(EnrichmentError, match="boom"):
        await provider.enrich(LISTING)


@pytest.mark.asyncio
async def test_text_enrichment_unparseable_response_raises():
    from src.providers.claude import ClaudeTextEnrichment

    provider = ClaudeTextEnrichment(FakeLLM("```json\n{broken"))

    with pytest.raises(EnrichmentError):
        await provider.enrich(LISTING)


@pytest.mark.asyncio
async def test_accepts_json_wrapped_in_a_markdown_fence():
    """Both prompts say "no markdown" and models still fence the output.

    Sonnet 5 wraps text-enrichment JSON in ```json fences where Opus 5 does
    not, so the instruction is a request, never a guarantee.
    """
    from src.providers.claude import ClaudeTextEnrichment

    fenced = "```json\n" + TEXT_RESPONSE + "\n```"
    provider = ClaudeTextEnrichment(FakeLLM(fenced))

    enrichment = await provider.enrich(LISTING)

    assert enrichment.tech_stack == ["AWS", "Docker", "GitHub Actions"]


@pytest.mark.asyncio
async def test_accepts_a_bare_fence_without_a_language_tag():
    fenced = "```\n" + TYPED_RESPONSE + "\n```"
    provider = ClaudeTypedDecisions(FakeLLM(fenced))

    decisions = await provider.decide(LISTING, profile="Senior DevOps Engineer.")

    assert decisions.fit_score == 0.82


@pytest.mark.asyncio
async def test_still_raises_on_genuinely_unparseable_output():
    provider = ClaudeTypedDecisions(FakeLLM("I can't help with that request."))

    with pytest.raises(EnrichmentError):
        await provider.decide(LISTING, profile="Senior DevOps Engineer.")

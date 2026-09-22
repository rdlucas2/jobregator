"""JevTypedDecisions maps one batched system_one() call onto Decisions.

Stubs the transport, not the SDK types: responses are built from the real
pydantic models so the mapping is validated against the actual schema.
"""

import pytest
from typesafe_sdk import ChoiceAnswer, NoulAnswer, ScoreAnswer, SystemOneResponse, Usage

from src.providers.jev import JevTypedDecisions

FIT_LEGEND = {
    0: "No match",
    1: "Weak match",
    2: "Plausible match",
    3: "Strong match",
    4: "Excellent match",
}

LISTING = {
    "title": "Senior DevOps Engineer",
    "company": "Acme Corp",
    "location": "Remote, USA",
    "description": "Fully remote platform role. Terraform, Kubernetes, AWS.",
}
PROFILE = "Senior DevOps Engineer, 15+ years. Fully remote, W2 only."


def build_response(score=3.2, score_confidence=0.81, **noul_overrides):
    nouls = {
        "requires_office_presence": 0.04,
        "requires_relocation": 0.02,
        "is_contract_or_freelance": 0.03,
    }
    nouls.update(noul_overrides)
    return SystemOneResponse(
        model="jev-1.13.0",
        usage=Usage(input_tokens=420, output_tokens=0),
        answers={
            "fit": ScoreAnswer(
                score=score,
                confidence=score_confidence,
                legend=FIT_LEGEND,
                probabilities={0: 0.01, 1: 0.04, 2: 0.15, 3: 0.60, 4: 0.20},
            ),
            "experience_level": ChoiceAnswer(
                choice="senior", confidence=0.88, probabilities={"senior": 0.88}
            ),
            "remote_policy": ChoiceAnswer(
                choice="remote", confidence=0.93, probabilities={"remote": 0.93}
            ),
            "job_type": ChoiceAnswer(
                choice="full_time", confidence=0.95, probabilities={"full_time": 0.95}
            ),
            **{k: NoulAnswer(noul=v) for k, v in nouls.items()},
        },
    )


class StubClient:
    def __init__(self, response=None):
        self._response = response or build_response()
        self.calls = 0
        self.state = None
        self.questions = None
        self.model_arg = None

    async def system_one(self, state, questions, *, model=None, **kwargs):
        self.calls += 1
        self.state = state
        self.questions = questions
        self.model_arg = model
        return self._response


@pytest.mark.asyncio
async def test_one_batched_call_produces_every_typed_decision():
    client = StubClient()
    provider = JevTypedDecisions(client)

    decisions = await provider.decide(LISTING, PROFILE)

    assert client.calls == 1, "all questions must ride in one request"
    assert decisions.experience_level == "senior"
    assert decisions.remote_policy == "remote"
    assert decisions.job_type == "full_time"
    assert decisions.requires_office_presence == 0.04
    assert decisions.requires_relocation == 0.02
    assert decisions.is_contract_or_freelance == 0.03
    assert decisions.provider == "jev"
    assert decisions.model == "jev-1.13.0"


@pytest.mark.asyncio
async def test_score_is_normalized_from_level_index_space():
    """Jev scores in level indices; fit_score is contractually 0.0-1.0."""
    provider = JevTypedDecisions(StubClient(build_response(score=3.2)))

    decisions = await provider.decide(LISTING, PROFILE)

    assert decisions.fit_score == pytest.approx(0.8)  # 3.2 / (5 - 1)


@pytest.mark.asyncio
@pytest.mark.parametrize("raw,expected", [(0.0, 0.0), (4.0, 1.0), (2.0, 0.5)])
async def test_normalization_endpoints(raw, expected):
    provider = JevTypedDecisions(StubClient(build_response(score=raw)))

    decisions = await provider.decide(LISTING, PROFILE)

    assert decisions.fit_score == pytest.approx(expected)


@pytest.mark.asyncio
async def test_divisor_comes_from_the_response_legend_not_a_constant():
    """Changing the rubric must not silently rescale every stored score."""
    response = build_response(score=1.0)
    response.answers["fit"] = ScoreAnswer(
        score=1.0,
        confidence=0.7,
        legend={0: "No", 1: "Maybe", 2: "Yes"},
        probabilities={0: 0.1, 1: 0.7, 2: 0.2},
    )
    provider = JevTypedDecisions(StubClient(response))

    decisions = await provider.decide(LISTING, PROFILE)

    assert decisions.fit_score == pytest.approx(0.5)  # 1.0 / (3 - 1), not / 4


@pytest.mark.asyncio
async def test_state_carries_the_profile_and_omits_the_location_field():
    """Remote-ness is judged from the description; `location` is the field the
    original prompt warned was unreliable, and omitting it keeps this provider's
    input identical across both MCP tools."""
    client = StubClient()
    provider = JevTypedDecisions(client)

    await provider.decide(LISTING, PROFILE)

    assert client.state["candidate_profile"] == PROFILE
    assert client.state["title"] == "Senior DevOps Engineer"
    assert "location" not in client.state


@pytest.mark.asyncio
async def test_long_descriptions_are_truncated_to_protect_the_token_budget():
    client = StubClient()
    provider = JevTypedDecisions(client, max_description_chars=100)

    await provider.decide({**LISTING, "description": "x" * 5000}, PROFILE)

    assert len(client.state["description"]) == 100


@pytest.mark.asyncio
async def test_every_choice_offers_an_escape_option():
    """Without one the model must pick a wrong label rather than decline."""
    from typesafe_sdk import Choice

    client = StubClient()
    await JevTypedDecisions(client).decide(LISTING, PROFILE)

    choices = {k: q for k, q in client.questions.items() if isinstance(q, Choice)}
    assert choices, "expected Choice questions"
    for name, question in choices.items():
        assert "unknown" in question.criteria, f"{name} cannot decline"


@pytest.mark.asyncio
async def test_no_question_is_phrased_as_a_negation():
    """Jev reads negations literally; the positive form is inverted in code."""
    client = StubClient()
    await JevTypedDecisions(client).decide(LISTING, PROFILE)

    for name, question in client.questions.items():
        text = str(question.instructions)
        assert " not " not in text.lower(), f"{name} is phrased negatively: {text}"
        assert "NOT" not in text, f"{name} is phrased negatively: {text}"


@pytest.mark.asyncio
async def test_the_pinned_model_is_sent_and_the_served_model_is_recorded():
    client = StubClient()
    provider = JevTypedDecisions(client, model="jev-1.13.0")

    decisions = await provider.decide(LISTING, PROFILE)

    assert client.model_arg == "jev-1.13.0"
    assert decisions.model == "jev-1.13.0"


@pytest.mark.asyncio
async def test_confidence_is_carried_through_for_the_calibrated_fields():
    provider = JevTypedDecisions(StubClient(build_response(score_confidence=0.81)))

    decisions = await provider.decide(LISTING, PROFILE)

    assert decisions.confidence["fit"] == 0.81
    assert decisions.confidence["remote_policy"] == 0.93


@pytest.mark.asyncio
async def test_transport_failure_raises_enrichment_error():
    class FailingClient:
        async def system_one(self, *a, **kw):
            raise ConnectionError("boom")

    with pytest.raises(Exception, match="boom"):
        await JevTypedDecisions(FailingClient()).decide(LISTING, PROFILE)


@pytest.mark.asyncio
async def test_a_missing_answer_raises_rather_than_defaulting():
    from src.providers.base import EnrichmentError

    response = build_response()
    del response.answers["remote_policy"]

    with pytest.raises(EnrichmentError, match="remote_policy"):
        await JevTypedDecisions(StubClient(response)).decide(LISTING, PROFILE)


@pytest.mark.asyncio
async def test_raw_probabilities_are_carried_for_threshold_tuning():
    """Phase 3 retunes FIT_SCORE_THRESHOLD against the real distribution, which
    needs the distribution, not just the winning label."""
    provider = JevTypedDecisions(StubClient(build_response()))

    decisions = await provider.decide(LISTING, PROFILE)

    assert decisions.probabilities["fit"][3] == pytest.approx(0.60)
    assert decisions.probabilities["remote_policy"]["remote"] == pytest.approx(0.93)

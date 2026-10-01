"""Jev-backed typed decisions.

Jev returns typed answers with calibrated probabilities and generates no text,
so it serves the bounded half of enrichment only. Every question about a listing
rides in one `system_one()` call: questions about a shared state are answered in
parallel, so batching is both cheaper and faster than asking serially.

Question wording follows Jev's constraints — positive phrasing only (negations
are read literally), an explicit escape option on every Choice so the model can
decline rather than guess, and no arithmetic or counting.
"""

from typesafe_sdk import Choice, Noul, Score

from src.providers.base import Decisions, EnrichmentError

PROVIDER_NAME = "jev"
DEFAULT_MODEL = "jev-1.13.0"

# `state` shares a 32k-token budget with the questions. Job descriptions are
# normally far below this; the cap exists so one pathological listing cannot
# fail the request.
DEFAULT_MAX_DESCRIPTION_CHARS = 20_000

FIT_LEVELS = [
    "No match: wrong discipline or seniority entirely",
    "Weak match: adjacent field, most of the profile's strengths unused",
    "Plausible match: overlapping skills, notable gaps in stack or seniority",
    "Strong match: core skills and seniority line up with the profile",
    "Excellent match: squarely the role the profile describes",
]

EXPERIENCE_LEVELS = {
    "junior": "Early career, 0-2 years",
    "mid": "Mid level, roughly 3-5 years",
    "senior": "Senior individual contributor",
    "lead": "Tech lead or team lead",
    "principal": "Principal or staff level",
    "unknown": "The listing does not indicate a level",
}

REMOTE_POLICIES = {
    "remote": "Fully remote with no in-office requirement",
    "hybrid": "Splits time between remote and an office",
    "onsite": "Requires working from an office or a specific site",
    "unknown": "The listing does not say",
}

JOB_TYPES = {
    "full_time": "Full-time employment",
    "part_time": "Part-time employment",
    "contract": "Contract, freelance, or temporary engagement",
    "unknown": "The listing does not say",
}


# Questions that report a confidence and a full distribution. Nouls do not:
# their probability is itself the confidence.
_CALIBRATED_FIELDS = ("fit", "experience_level", "remote_policy", "job_type")


def _questions() -> dict:
    return {
        "fit": Score(
            instructions="How well this role matches the candidate profile on "
            "discipline, seniority, and technology overlap. Judge the match "
            "itself; remote policy is scored separately.",
            criteria=FIT_LEVELS,
        ),
        "experience_level": Choice(
            instructions="The seniority this role is pitched at",
            criteria=EXPERIENCE_LEVELS,
        ),
        "remote_policy": Choice(
            instructions="Where the work is performed, judged from the body of "
            "the description rather than any remote tag",
            criteria=REMOTE_POLICIES,
        ),
        "job_type": Choice(
            instructions="The employment arrangement offered",
            criteria=JOB_TYPES,
        ),
        # Phrased positively on purpose: Jev reads a negation literally.
        "requires_office_presence": Noul(
            instructions="The description states an in-office, hybrid, or "
            "on-site attendance requirement"
        ),
        "requires_relocation": Noul(
            instructions="The description requires relocating or being based in "
            "a particular place"
        ),
        "is_contract_or_freelance": Noul(
            instructions="This is a contract, freelance, or otherwise non-W2 "
            "engagement"
        ),
    }


class JevTypedDecisions:
    """Answers every bounded question about a listing in one Jev call.

    Any server speaking Jev's /v1/systemone protocol works; `provider_name` is
    only the label stored with each decision (Laya reuses this class).
    """

    def __init__(
        self,
        client,
        model: str = DEFAULT_MODEL,
        max_description_chars: int = DEFAULT_MAX_DESCRIPTION_CHARS,
        provider_name: str = PROVIDER_NAME,
    ):
        self._client = client
        self._provider_name = provider_name
        self._model = model
        self._max_description_chars = max_description_chars

    def _state(self, listing: dict, profile: str) -> dict:
        # Only what the judgment needs. Padding state with material the
        # questions do not concern measurably lowers accuracy.
        description = listing.get("description", "") or ""
        return {
            "title": listing.get("title", ""),
            "company": listing.get("company", ""),
            "description": description[: self._max_description_chars],
            "candidate_profile": profile,
        }

    async def decide(self, listing: dict, profile: str) -> Decisions:
        try:
            response = await self._client.system_one(
                state=self._state(listing, profile),
                questions=_questions(),
                model=self._model,
            )
        except Exception as exc:
            raise EnrichmentError(f"jev request failed: {exc}") from exc

        answers = response.answers
        try:
            fit = answers["fit"]
            return Decisions(
                fit_score=_normalize_score(fit),
                experience_level=answers["experience_level"].choice,
                remote_policy=answers["remote_policy"].choice,
                job_type=answers["job_type"].choice,
                requires_office_presence=answers["requires_office_presence"].noul,
                requires_relocation=answers["requires_relocation"].noul,
                is_contract_or_freelance=answers["is_contract_or_freelance"].noul,
                confidence={
                    name: answers[name].confidence
                    for name in _CALIBRATED_FIELDS
                },
                probabilities={
                    name: dict(answers[name].probabilities)
                    for name in _CALIBRATED_FIELDS
                },
                provider=self._provider_name,
                model=getattr(response, "model", self._model),
            )
        except (KeyError, AttributeError) as exc:
            raise EnrichmentError(f"jev response missing answer: {exc}") from exc


def _normalize_score(answer) -> float:
    """Map a Score from level-index space onto the 0.0-1.0 fit contract.

    The divisor comes from the response's own legend rather than a constant, so
    changing the rubric cannot silently rescale every stored score.
    """
    levels = len(answer.legend)
    if levels < 2:
        raise EnrichmentError(f"fit legend needs at least 2 levels, got {levels}")
    return max(0.0, min(1.0, answer.score / (levels - 1)))

"""Claude-backed providers.

Claude serves both halves of enrichment: it can pick from a fixed set *and*
write prose. It is the only implementation of `TextEnrichmentProvider`, and the
fallback implementation of `TypedDecisionProvider`.
"""

import json

from src.providers.base import Decisions, EnrichmentError, TextEnrichment

PROVIDER_NAME = "claude"

TYPED_DECISIONS_PROMPT = """Judge this job listing against the candidate profile.

## Job Listing
Title: {title}
Company: {company}
Description: {description}

## Candidate Profile
{profile}

Return a JSON object with exactly these fields:
- fit_score: float 0.0-1.0, how well the role matches the profile on its merits
  (experience, tech stack, seniority, compensation). Judge the match only — do
  NOT penalize for remote/on-site here, that is handled separately.
- experience_level: one of "junior", "mid", "senior", "lead", "principal"
- remote_policy: one of "remote", "hybrid", "onsite", "unknown"
- job_type: one of "full_time", "part_time", "contract", "unknown"
- requires_office_presence: float 0.0-1.0, probability the description states an
  in-office, hybrid, or on-site attendance requirement. Judge from the body
  text: listings are routinely tagged remote and then require office days.
- requires_relocation: float 0.0-1.0, probability the description requires
  relocating or being based in a specific place
- is_contract_or_freelance: float 0.0-1.0, probability this is a contract,
  freelance, or non-W2 engagement

Return ONLY valid JSON, no markdown or explanation."""


async def _complete_json(llm, prompt: str) -> dict:
    """Call Claude and parse its reply as JSON, or raise EnrichmentError.

    Both Claude providers need this and neither may return a neutral default on
    failure: a silently-defaulted answer is indistinguishable from a real one.
    """
    try:
        response = await llm.complete(prompt)
    except Exception as exc:
        raise EnrichmentError(f"claude request failed: {exc}") from exc

    try:
        return json.loads(response)
    except (json.JSONDecodeError, TypeError) as exc:
        raise EnrichmentError(f"claude returned unparseable JSON: {exc}") from exc


def _probability(raw, field_name: str) -> float:
    try:
        return max(0.0, min(1.0, float(raw)))
    except (TypeError, ValueError) as exc:
        raise EnrichmentError(f"{field_name} was not a number: {raw!r}") from exc


class ClaudeTypedDecisions:
    """Produces every typed decision in a single Claude call."""

    def __init__(self, llm):
        self._llm = llm

    async def decide(self, listing: dict, profile: str) -> Decisions:
        prompt = TYPED_DECISIONS_PROMPT.format(
            title=listing.get("title", ""),
            company=listing.get("company", ""),
            description=listing.get("description", ""),
            profile=profile,
        )

        raw = await _complete_json(self._llm, prompt)

        try:
            return Decisions(
                fit_score=_probability(raw["fit_score"], "fit_score"),
                experience_level=str(raw["experience_level"]),
                remote_policy=str(raw["remote_policy"]),
                job_type=str(raw["job_type"]),
                requires_office_presence=_probability(
                    raw["requires_office_presence"], "requires_office_presence"
                ),
                requires_relocation=_probability(
                    raw["requires_relocation"], "requires_relocation"
                ),
                is_contract_or_freelance=_probability(
                    raw["is_contract_or_freelance"], "is_contract_or_freelance"
                ),
                provider=PROVIDER_NAME,
                model=getattr(self._llm, "model", ""),
            )
        except KeyError as exc:
            raise EnrichmentError(f"claude response missing field: {exc}") from exc


TEXT_ENRICHMENT_PROMPT = """Extract structured detail from this job listing.

Title: {title}
Company: {company}
Location: {location}
Description: {description}

Return a JSON object with exactly these fields:
- skills: list of required or preferred technical skills
- tech_stack: list of specific technologies and tools mentioned
- remote_flags: list of verbatim phrases from the description suggesting the
  role is NOT fully remote (e.g. "3 days in office", "must relocate to Austin").
  Empty list if none appear.
- summary: one-sentence summary of the role

Return ONLY valid JSON, no markdown or explanation."""


class ClaudeTextEnrichment:
    """Produces the open-ended fields a typed-decision model cannot emit."""

    def __init__(self, llm):
        self._llm = llm

    async def enrich(self, listing: dict) -> TextEnrichment:
        prompt = TEXT_ENRICHMENT_PROMPT.format(
            title=listing.get("title", ""),
            company=listing.get("company", ""),
            location=listing.get("location", ""),
            description=listing.get("description", ""),
        )

        raw = await _complete_json(self._llm, prompt)

        return TextEnrichment(
            skills=list(raw.get("skills", [])),
            tech_stack=list(raw.get("tech_stack", [])),
            remote_flags=list(raw.get("remote_flags", [])),
            summary=str(raw.get("summary", "")),
            provider=PROVIDER_NAME,
            model=getattr(self._llm, "model", ""),
        )

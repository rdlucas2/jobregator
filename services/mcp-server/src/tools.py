"""Enrichment tools.

These compose providers; they own no prompts. Policy that used to be phrased as
prompt instructions lives here as code, so it applies identically no matter
which provider answered — including providers that accept no prose at all.
"""

# The candidate requires a fully remote role. A listing that reads well but
# expects office attendance is capped rather than rejected, so it still shows
# up in the dashboard below the notification threshold.
OFFICE_PRESENCE_THRESHOLD = 0.5
NON_REMOTE_SCORE_CAP = 0.3


def apply_remote_policy(decisions) -> float:
    """Cap the fit score for roles that expect office attendance."""
    if decisions.requires_office_presence > OFFICE_PRESENCE_THRESHOLD:
        return min(decisions.fit_score, NON_REMOTE_SCORE_CAP)
    return decisions.fit_score


def synthesize_reasoning(decisions, final_score: float) -> str:
    """Explain a score from the decisions that produced it.

    Providers that return typed answers emit no prose, so the explanation is
    built here. It cites the probabilities that drove the outcome, which is
    more auditable than a generated sentence and costs nothing.
    """
    parts = [f"Fit {final_score:.2f}"]
    if final_score < decisions.fit_score:
        parts.append(
            f"(capped from {decisions.fit_score:.2f}: office presence expected, "
            f"p={decisions.requires_office_presence:.2f})"
        )
    parts.append(
        f"— {decisions.experience_level}, {decisions.remote_policy}, {decisions.job_type}"
    )
    if decisions.requires_relocation > OFFICE_PRESENCE_THRESHOLD:
        parts.append(f"; relocation expected (p={decisions.requires_relocation:.2f})")
    if decisions.is_contract_or_freelance > OFFICE_PRESENCE_THRESHOLD:
        parts.append(f"; contract or freelance (p={decisions.is_contract_or_freelance:.2f})")
    return " ".join(parts)


async def score_fit(listing: dict, profile: str, typed_provider) -> dict:
    """Score how well a listing matches the candidate profile."""
    decisions = await typed_provider.decide(listing, profile)
    score = apply_remote_policy(decisions)
    return {
        "score": score,
        "reasoning": synthesize_reasoning(decisions, score),
        "provider": decisions.provider,
        "model": decisions.model,
        "confidence": decisions.confidence,
    }


async def analyze_job_listing(
    listing: dict, profile: str, typed_provider, text_provider
) -> dict:
    """Extract structured data for a listing from both providers.

    The typed fields and the prose come from different models, but the tool's
    output shape is fixed by the MCP contract, so they are merged here.
    """
    decisions = await typed_provider.decide(listing, profile)
    text = await text_provider.enrich(listing)

    return {
        "skills": text.skills,
        "experience_level": decisions.experience_level,
        "remote_policy": decisions.remote_policy,
        "remote_flags": text.remote_flags,
        "tech_stack": text.tech_stack,
        "job_type": decisions.job_type,
        "summary": text.summary,
        "provider": decisions.provider,
        "model": decisions.model,
        "text_provider": text.provider,
        "text_model": text.model,
    }

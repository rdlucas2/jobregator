import json


ANALYZE_PROMPT_TEMPLATE = """Analyze this job listing and extract structured data.

Job Title: {title}
Company: {company}
Location: {location}
Description: {description}

Return a JSON object with these fields:
- skills: list of required/preferred technical skills
- experience_level: one of "junior", "mid", "senior", "lead", "principal"
- remote_policy: one of "remote", "hybrid", "onsite", "unknown". IMPORTANT: Read the FULL description carefully. Many listings are tagged "remote" in the title or location but then require office attendance, relocation, or hybrid schedules in the body. If the description mentions ANY of: required days in office, hybrid schedule, must relocate, must be based/located in a specific city, on-site requirements — classify as "hybrid" or "onsite", NOT "remote". Only classify as "remote" if the role is truly 100% remote with no in-office requirement.
- remote_flags: list of any phrases from the description that suggest the role is NOT fully remote (e.g. "3 days in office", "must relocate to Austin"). Empty list if truly remote.
- tech_stack: list of specific technologies/tools mentioned
- job_type: one of "full_time", "part_time", "contract", "unknown"
- summary: one-sentence summary of the role

Return ONLY valid JSON, no markdown or explanation."""

SCORE_FIT_PROMPT_TEMPLATE = """Score how well this job listing matches the candidate profile.

## Job Listing
Title: {title}
Company: {company}
Description: {description}

## Candidate Profile
{profile}

IMPORTANT: The candidate requires a fully remote position. If the description contains ANY language suggesting hybrid, on-site requirements, office days, relocation, or "must be based in" a specific location, significantly penalize the score (cap at 0.3 max). Only give high scores to roles that are clearly 100% remote.

Return a JSON object with:
- score: a float from 0.0 to 1.0 (0 = no match, 1 = perfect match)
- reasoning: 1-2 sentences explaining the score. If the role is not truly remote, explicitly call this out.

Return ONLY valid JSON, no markdown or explanation."""


async def analyze_job_listing(listing: dict, llm) -> dict:
    """Analyze a job listing and return structured data."""
    prompt = ANALYZE_PROMPT_TEMPLATE.format(
        title=listing.get("title", ""),
        company=listing.get("company", ""),
        location=listing.get("location", ""),
        description=listing.get("description", ""),
    )

    try:
        response = await llm.complete(prompt)
        result = json.loads(response)
        return result
    except (json.JSONDecodeError, ValueError):
        return {"error": "Failed to parse LLM response", "raw_response": response}


async def score_fit(listing: dict, profile: str, llm) -> dict:
    """Score how well a listing matches the candidate profile."""
    prompt = SCORE_FIT_PROMPT_TEMPLATE.format(
        title=listing.get("title", ""),
        company=listing.get("company", ""),
        description=listing.get("description", ""),
        profile=profile,
    )

    try:
        response = await llm.complete(prompt)
        result = json.loads(response)
        # Clamp score to [0.0, 1.0]
        result["score"] = max(0.0, min(1.0, float(result["score"])))
        return result
    except (json.JSONDecodeError, ValueError, KeyError):
        return {"score": 0.0, "reasoning": "Failed to parse LLM response", "error": True}

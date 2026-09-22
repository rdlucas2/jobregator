"""The refactor must not cost more than it replaces.

Before: analyze_job = 1 Claude call, score_job_fit = 1 Claude call.
After:  typed decisions = 1 call (memoized across both tools), text = 1 call.
"""

import json
import pytest

from src.providers.factory import build_text_provider, build_typed_provider
from src.tools import analyze_job_listing, score_fit


class CountingLLM:
    model = "claude-test-1"

    def __init__(self):
        self.prompts = []

    async def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if "fit_score" in prompt:
            return json.dumps({
                "fit_score": 0.82,
                "experience_level": "senior",
                "remote_policy": "remote",
                "job_type": "full_time",
                "requires_office_presence": 0.03,
                "requires_relocation": 0.01,
                "is_contract_or_freelance": 0.02,
            })
        return json.dumps({
            "skills": ["Terraform"],
            "tech_stack": ["AWS"],
            "remote_flags": [],
            "summary": "Senior platform role.",
        })


@pytest.mark.asyncio
async def test_enriching_one_listing_costs_two_claude_calls():
    llm = CountingLLM()
    typed = build_typed_provider("claude", llm, cached=True)
    text = build_text_provider(llm)

    # Exactly how the worker drives the two MCP tools, in order.
    analysis = await analyze_job_listing(
        {"title": "Senior DevOps Engineer", "company": "Acme",
         "location": "Remote, USA", "description": "Fully remote."},
        profile="Senior DevOps Engineer.",
        typed_provider=typed,
        text_provider=text,
    )
    scoring = await score_fit(
        {"title": "Senior DevOps Engineer", "company": "Acme",
         "description": "Fully remote."},
        "Senior DevOps Engineer.",
        typed,
    )

    assert len(llm.prompts) == 2, f"expected 2 Claude calls, got {len(llm.prompts)}"
    assert analysis["experience_level"] == "senior"
    assert scoring["score"] == 0.82

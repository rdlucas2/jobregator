import json
import pytest

from src.tools import analyze_job_listing, score_fit


class FakeLLM:
    """Mock LLM client that returns canned responses."""

    def __init__(self, response_text: str):
        self.response_text = response_text
        self.last_prompt = None

    async def complete(self, prompt: str) -> str:
        self.last_prompt = prompt
        return self.response_text


@pytest.mark.asyncio
async def test_analyze_job_listing_returns_structured_data():
    fake_response = json.dumps({
        "skills": ["Kubernetes", "Terraform", "CI/CD", "Python"],
        "experience_level": "senior",
        "remote_policy": "remote",
        "tech_stack": ["AWS", "Docker", "GitHub Actions"],
        "job_type": "full_time",
        "summary": "Senior DevOps role focused on cloud infrastructure.",
    })
    llm = FakeLLM(fake_response)

    listing = {
        "title": "Senior DevOps Engineer",
        "company": "Acme Corp",
        "description": "We need a senior DevOps engineer with K8s and Terraform...",
        "location": "Remote, USA",
    }

    result = await analyze_job_listing(listing, llm=llm)

    assert result["skills"] == ["Kubernetes", "Terraform", "CI/CD", "Python"]
    assert result["experience_level"] == "senior"
    assert result["remote_policy"] == "remote"
    assert "remote_policy" in llm.last_prompt.lower() or "remote" in llm.last_prompt.lower()
    assert result["tech_stack"] == ["AWS", "Docker", "GitHub Actions"]
    assert "DevOps" in result["summary"]
    # Verify the LLM was called with listing context
    assert "Senior DevOps Engineer" in llm.last_prompt
    assert "Acme Corp" in llm.last_prompt


@pytest.mark.asyncio
async def test_analyze_prompt_includes_remote_detection_instructions():
    fake_response = json.dumps({
        "skills": [],
        "experience_level": "senior",
        "remote_policy": "hybrid",
        "remote_flags": ["3 days in office required"],
        "tech_stack": [],
        "job_type": "full_time",
        "summary": "A hybrid role.",
    })
    llm = FakeLLM(fake_response)

    listing = {
        "title": "DevOps Engineer",
        "company": "Corp",
        "description": "Remote-friendly but 3 days in office required.",
        "location": "Remote",
    }

    result = await analyze_job_listing(listing, llm=llm)

    assert result["remote_policy"] == "hybrid"
    assert result["remote_flags"] == ["3 days in office required"]
    # Verify the prompt instructs careful remote analysis
    assert "hybrid" in llm.last_prompt.lower()


@pytest.mark.asyncio
async def test_score_fit_prompt_penalizes_non_remote():
    fake_response = json.dumps({
        "score": 0.25,
        "reasoning": "Role requires 3 days in office, not truly remote.",
    })
    llm = FakeLLM(fake_response)

    listing = {
        "title": "DevOps Engineer",
        "company": "Corp",
        "description": "Must be in NYC office 3 days per week.",
    }

    result = await score_fit(listing, "Remote-only senior engineer.", llm=llm)

    assert result["score"] == 0.25
    # Verify the prompt mentions remote penalty
    assert "remote" in llm.last_prompt.lower()
    assert "penalize" in llm.last_prompt.lower()


@pytest.mark.asyncio
async def test_score_fit_returns_score_and_reasoning():
    fake_response = json.dumps({
        "score": 0.85,
        "reasoning": "Strong match for K8s and Terraform skills. CI/CD experience aligns well.",
    })
    llm = FakeLLM(fake_response)

    listing = {
        "title": "Senior DevOps Engineer",
        "company": "Acme Corp",
        "description": "We need a senior DevOps engineer with K8s and Terraform...",
    }
    profile = "Senior DevOps / Platform Engineer with 10+ years experience. Core strengths: K8s, Terraform, CI/CD."

    result = await score_fit(listing, profile, llm=llm)

    assert result["score"] == 0.85
    assert "K8s" in result["reasoning"]
    # Verify both listing and profile were sent to the LLM
    assert "Senior DevOps Engineer" in llm.last_prompt
    assert "Platform Engineer" in llm.last_prompt


@pytest.mark.asyncio
async def test_score_fit_clamps_score_to_valid_range():
    fake_response = json.dumps({
        "score": 1.5,
        "reasoning": "Unreasonably high score.",
    })
    llm = FakeLLM(fake_response)

    result = await score_fit({"title": "Test", "description": "Test"}, "profile", llm=llm)

    assert result["score"] == 1.0


@pytest.mark.asyncio
async def test_analyze_handles_malformed_llm_response():
    llm = FakeLLM("This is not JSON at all")

    listing = {"title": "Test Job", "description": "A job"}

    result = await analyze_job_listing(listing, llm=llm)

    assert "error" in result

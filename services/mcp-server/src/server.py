import json
import logging
import os

import yaml
from mcp.server.fastmcp import FastMCP

from src.llm import ClaudeLLM
from src.tools import analyze_job_listing, score_fit

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

PROFILE_PATH = os.environ.get("PROFILE_PATH", "/config/profile.yaml")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514")

mcp = FastMCP("jobregator-enrichment")


def load_profile_text(path: str) -> str:
    with open(path) as f:
        config = yaml.safe_load(f)
    return config.get("profile", "")


# Load profile and LLM at module level
_profile_text = ""
_llm = None


def _get_llm():
    global _llm
    if _llm is None:
        if not ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY must be set")
        _llm = ClaudeLLM(api_key=ANTHROPIC_API_KEY, model=CLAUDE_MODEL)
    return _llm


def _get_profile():
    global _profile_text
    if not _profile_text:
        _profile_text = load_profile_text(PROFILE_PATH)
        log.info("loaded profile from %s (%d chars)", PROFILE_PATH, len(_profile_text))
    return _profile_text


@mcp.tool()
async def analyze_job(
    title: str,
    company: str,
    location: str,
    description: str,
) -> str:
    """Analyze a job listing and extract structured data including skills,
    experience level, remote policy, tech stack, and a summary."""
    listing = {
        "title": title,
        "company": company,
        "location": location,
        "description": description,
    }
    result = await analyze_job_listing(listing, llm=_get_llm())
    return json.dumps(result)


@mcp.tool()
async def score_job_fit(
    title: str,
    company: str,
    description: str,
) -> str:
    """Score how well a job listing matches the candidate's profile.
    Returns a score from 0.0 to 1.0 with reasoning."""
    listing = {
        "title": title,
        "company": company,
        "description": description,
    }
    result = await score_fit(listing, _get_profile(), llm=_get_llm())
    return json.dumps(result)


def main():
    log.info("starting MCP enrichment server")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

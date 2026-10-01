import json
import logging
import os

import yaml
from mcp.server.fastmcp import FastMCP

from src.llm import DEFAULT_MODEL, ClaudeLLM
from src.providers.factory import (
    DEFAULT_LAYA_MODEL,
    build_text_provider,
    build_typed_provider,
)
from src.tools import analyze_job_listing, score_fit

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

PROFILE_PATH = os.environ.get("PROFILE_PATH", "/config/profile.yaml")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", DEFAULT_MODEL)
# Which model answers the bounded questions. Defaults to "claude" while
# TypeSafe signups are closed; set "jev" once a TYPESAFE_API_KEY exists. The
# jev path is implemented and tested, just unexercised against the live API.
# "laya" needs no cloud key: it targets a self-hosted laya-server (LAYA_BASE_URL).
# See plans/jev-typed-decisions.md.
TYPED_PROVIDER = os.environ.get("ENRICHMENT_TYPED_PROVIDER", "claude")
TYPESAFE_API_KEY = os.environ.get("TYPESAFE_API_KEY", "")
# Pinned rather than "jev-latest": routing branches on probability thresholds,
# and an alias that moves underneath us changes behavior silently.
JEV_MODEL = os.environ.get("JEV_MODEL", "jev-1.13.0")
# Laya (open-source, runs locally) serves Jev's wire protocol. Point this at a
# `laya-serve` instance, e.g. http://host.docker.internal:8000.
LAYA_BASE_URL = os.environ.get("LAYA_BASE_URL", "")
LAYA_API_KEY = os.environ.get("LAYA_API_KEY", "")
LAYA_MODEL = os.environ.get("LAYA_MODEL", DEFAULT_LAYA_MODEL)

mcp = FastMCP("jobregator-enrichment")


def load_profile_text(path: str) -> str:
    with open(path) as f:
        config = yaml.safe_load(f)
    return config.get("profile", "")


# Load profile, LLM, and providers at module level
_profile_text = ""
_llm = None
_typed_provider = None
_text_provider = None
_typesafe_client = None


def _get_llm():
    global _llm
    if _llm is None:
        if not ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY must be set")
        _llm = ClaudeLLM(api_key=ANTHROPIC_API_KEY, model=CLAUDE_MODEL)
    return _llm


def _get_typesafe_client():
    global _typesafe_client
    if _typesafe_client is None:
        if not TYPESAFE_API_KEY:
            raise RuntimeError(
                "TYPESAFE_API_KEY must be set when ENRICHMENT_TYPED_PROVIDER=jev "
                "(set ENRICHMENT_TYPED_PROVIDER=claude to fall back to Claude)"
            )
        from typesafe_sdk import AsyncTypeSafeClient

        _typesafe_client = AsyncTypeSafeClient(api_key=TYPESAFE_API_KEY)
    return _typesafe_client


def _get_laya_client():
    if not LAYA_BASE_URL:
        raise RuntimeError(
            "LAYA_BASE_URL must be set when ENRICHMENT_TYPED_PROVIDER=laya "
            "(e.g. http://host.docker.internal:8000)"
        )
    global _typesafe_client
    if _typesafe_client is None:
        from typesafe_sdk import AsyncTypeSafeClient

        _typesafe_client = AsyncTypeSafeClient(
            # The SDK rejects an empty key; laya-serve ignores it unless it was
            # started with LAYA_API_KEY.
            api_key=LAYA_API_KEY or "laya-local",
            base_url=LAYA_BASE_URL,
        )
    return _typesafe_client


def _get_typed_provider():
    """The typed-decision provider, memoized across the two MCP tools.

    Both tools need the same decisions for a given listing, so the provider is
    wrapped in a cache to keep that one model round trip rather than two.
    """
    global _typed_provider
    if _typed_provider is None:
        kind = (TYPED_PROVIDER or "").strip().lower()
        wants_jev = kind == "jev"
        wants_laya = kind == "laya"
        typesafe_client = None
        if wants_jev:
            typesafe_client = _get_typesafe_client()
        elif wants_laya:
            typesafe_client = _get_laya_client()
        _typed_provider = build_typed_provider(
            TYPED_PROVIDER,
            llm=None if (wants_jev or wants_laya) else _get_llm(),
            typesafe_client=typesafe_client,
            jev_model=JEV_MODEL,
            laya_model=LAYA_MODEL,
            cached=True,
        )
        log.info(
            "typed decision provider: %s%s",
            TYPED_PROVIDER,
            f" ({JEV_MODEL})" if wants_jev else f" ({LAYA_MODEL})" if wants_laya else "",
        )
    return _typed_provider


def _get_text_provider():
    global _text_provider
    if _text_provider is None:
        _text_provider = build_text_provider(_get_llm())
    return _text_provider


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
    result = await analyze_job_listing(
        listing,
        profile=_get_profile(),
        typed_provider=_get_typed_provider(),
        text_provider=_get_text_provider(),
    )
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
    result = await score_fit(listing, _get_profile(), _get_typed_provider())
    return json.dumps(result)


def main():
    log.info("starting MCP enrichment server")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

import pytest

from src.providers.claude import ClaudeTextEnrichment, ClaudeTypedDecisions
from src.providers.factory import build_text_provider, build_typed_provider


class FakeLLM:
    model = "claude-test-1"

    async def complete(self, prompt: str) -> str:
        return "{}"


def test_builds_the_claude_typed_provider_by_name():
    provider = build_typed_provider("claude", llm=FakeLLM())

    assert isinstance(provider, ClaudeTypedDecisions)


def test_typed_provider_is_wrapped_in_the_decision_cache():
    """Every provider gets memoized, not just Claude — the duplicate-call
    problem comes from the MCP tool surface, not from any one provider."""
    from src.providers.cache import CachingTypedDecisions

    provider = build_typed_provider("claude", llm=FakeLLM(), cached=True)

    assert isinstance(provider, CachingTypedDecisions)


def test_unknown_provider_name_fails_with_the_valid_options():
    with pytest.raises(ValueError, match="claude"):
        build_typed_provider("gpt", llm=FakeLLM())


def test_provider_name_is_case_and_whitespace_insensitive():
    assert isinstance(build_typed_provider("  CLAUDE ", llm=FakeLLM()), ClaudeTypedDecisions)


def test_builds_the_claude_text_provider():
    assert isinstance(build_text_provider(llm=FakeLLM()), ClaudeTextEnrichment)


class StubTypeSafeClient:
    async def system_one(self, *a, **kw):
        raise AssertionError("not called during construction")


def test_builds_the_jev_typed_provider_by_name():
    from src.providers.jev import JevTypedDecisions

    provider = build_typed_provider("jev", typesafe_client=StubTypeSafeClient())

    assert isinstance(provider, JevTypedDecisions)


def test_jev_provider_is_pinned_to_the_configured_model():
    provider = build_typed_provider(
        "jev", typesafe_client=StubTypeSafeClient(), jev_model="jev-1.13.0"
    )

    assert provider._model == "jev-1.13.0"


def test_asking_for_jev_without_a_client_fails_loudly():
    with pytest.raises(ValueError, match="typesafe_client"):
        build_typed_provider("jev")


def test_asking_for_claude_without_an_llm_fails_loudly():
    with pytest.raises(ValueError, match="llm"):
        build_typed_provider("claude")


def test_unknown_provider_error_lists_both_options():
    with pytest.raises(ValueError, match="claude, jev"):
        build_typed_provider("gpt", llm=FakeLLM())

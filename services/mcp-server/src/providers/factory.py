"""Provider selection.

`ENRICHMENT_TYPED_PROVIDER` chooses which model answers the bounded questions.
There is deliberately no equivalent knob for text enrichment: a config value
with one legal value is noise. Add one if a second text provider ever exists.
"""

from src.providers.cache import CachingTypedDecisions
from src.providers.claude import ClaudeTextEnrichment, ClaudeTypedDecisions

CLAUDE = "claude"

_TYPED_BUILDERS = {
    CLAUDE: lambda llm: ClaudeTypedDecisions(llm),
}


def build_typed_provider(name: str, llm, cached: bool = False):
    """Build the typed-decision provider named by config."""
    key = (name or "").strip().lower()

    builder = _TYPED_BUILDERS.get(key)
    if builder is None:
        valid = ", ".join(sorted(_TYPED_BUILDERS))
        raise ValueError(
            f"unknown typed decision provider {name!r}; valid options are: {valid}"
        )

    provider = builder(llm)
    return CachingTypedDecisions(provider) if cached else provider


def build_text_provider(llm):
    """Build the text-enrichment provider. Claude is the only implementation."""
    return ClaudeTextEnrichment(llm)

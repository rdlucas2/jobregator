"""Provider selection.

`ENRICHMENT_TYPED_PROVIDER` chooses which model answers the bounded questions.
There is deliberately no equivalent knob for text enrichment: a config value
with one legal value is noise. Add one if a second text provider ever exists.

Clients are passed in rather than constructed here, so selection stays testable
without credentials and environment reading stays in one place (`server.py`).
"""

from src.providers.cache import CachingTypedDecisions
from src.providers.claude import ClaudeTextEnrichment, ClaudeTypedDecisions
from src.providers.jev import DEFAULT_MODEL as DEFAULT_JEV_MODEL
from src.providers.jev import JevTypedDecisions

CLAUDE = "claude"
JEV = "jev"

VALID_TYPED_PROVIDERS = (CLAUDE, JEV)


def _require(value, name: str, provider: str):
    if value is None:
        raise ValueError(f"the {provider!r} typed provider requires {name}")
    return value


def build_typed_provider(
    name: str,
    llm=None,
    typesafe_client=None,
    jev_model: str = DEFAULT_JEV_MODEL,
    cached: bool = False,
):
    """Build the typed-decision provider named by config."""
    key = (name or "").strip().lower()

    if key == CLAUDE:
        provider = ClaudeTypedDecisions(_require(llm, "llm", CLAUDE))
    elif key == JEV:
        provider = JevTypedDecisions(
            _require(typesafe_client, "typesafe_client", JEV), model=jev_model
        )
    else:
        valid = ", ".join(VALID_TYPED_PROVIDERS)
        raise ValueError(
            f"unknown typed decision provider {name!r}; valid options are: {valid}"
        )

    return CachingTypedDecisions(provider) if cached else provider


def build_text_provider(llm):
    """Build the text-enrichment provider. Claude is the only implementation."""
    return ClaudeTextEnrichment(llm)

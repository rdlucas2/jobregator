"""Interfaces and value types for the enrichment providers.

Enrichment splits into two kinds of work, and the split is by *kind*, not by
vendor:

- **Typed decisions** — bounded answers (a score, a handful of enums, a few
  probabilities). Servable by any model that can pick from a fixed set, so this
  has more than one implementation.
- **Text enrichment** — prose and open-ended extraction. Requires a model that
  generates strings, so Claude is the only implementation.
"""

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


class EnrichmentError(RuntimeError):
    """A provider could not produce a usable answer.

    Raised rather than returning a neutral default: a silent 0.0 fit score is
    indistinguishable from a genuine rejection and suppresses the listing's
    notification without trace.
    """


@dataclass(frozen=True)
class Decisions:
    """Every bounded-answer field, produced by one provider round trip."""

    fit_score: float
    experience_level: str
    remote_policy: str
    job_type: str
    requires_office_presence: float
    requires_relocation: float
    is_contract_or_freelance: float
    confidence: dict[str, float] = field(default_factory=dict)
    # Full distribution per question, when the provider reports one. Kept for
    # threshold tuning: the winning label alone cannot tell you how close the
    # call was.
    probabilities: dict[str, dict] = field(default_factory=dict)
    provider: str = ""
    model: str = ""


@dataclass(frozen=True)
class TextEnrichment:
    """The open-ended fields, which only a text-generating model can produce."""

    skills: list[str] = field(default_factory=list)
    tech_stack: list[str] = field(default_factory=list)
    remote_flags: list[str] = field(default_factory=list)
    summary: str = ""
    provider: str = ""
    model: str = ""


@runtime_checkable
class TypedDecisionProvider(Protocol):
    async def decide(self, listing: dict, profile: str) -> Decisions: ...


@runtime_checkable
class TextEnrichmentProvider(Protocol):
    async def enrich(self, listing: dict) -> TextEnrichment: ...

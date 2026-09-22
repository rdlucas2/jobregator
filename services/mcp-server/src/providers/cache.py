"""Memoization for typed decisions.

The MCP surface exposes `analyze_job` and `score_job_fit` as separate tools and
the worker calls both for every listing, but a provider answers every typed
question about a listing in one round trip. Without memoization that round trip
happens twice per listing.

The cache is keyed on the listing content and the profile together, since both
feed the judgment. It is deliberately small: the access pattern is two lookups
in quick succession for the same listing, so it exists to collapse those, not to
serve traffic over time.
"""

import hashlib
import json
from collections import OrderedDict

from src.providers.base import Decisions

DEFAULT_MAXSIZE = 32

# Fields that actually reach the typed provider. This must stay in step with
# TYPED_DECISIONS_PROMPT: a key built from fields the provider never sees would
# miss whenever a caller omits one, which is exactly what happens between
# analyze_job (passes location) and score_job_fit (does not).
_KEYED_FIELDS = ("title", "company", "description")


def _cache_key(listing: dict, profile: str) -> str:
    payload = json.dumps(
        {f: listing.get(f, "") for f in _KEYED_FIELDS} | {"profile": profile},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


class CachingTypedDecisions:
    """Wraps any TypedDecisionProvider, collapsing repeat lookups."""

    def __init__(self, inner, maxsize: int = DEFAULT_MAXSIZE):
        self._inner = inner
        self._maxsize = maxsize
        self._entries: OrderedDict[str, Decisions] = OrderedDict()

    async def decide(self, listing: dict, profile: str) -> Decisions:
        key = _cache_key(listing, profile)

        if key in self._entries:
            self._entries.move_to_end(key)
            return self._entries[key]

        decisions = await self._inner.decide(listing, profile)

        self._entries[key] = decisions
        if len(self._entries) > self._maxsize:
            self._entries.popitem(last=False)
        return decisions

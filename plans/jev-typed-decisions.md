# Plan: Pluggable Typed-Decision Provider (Claude / Jev)

> Source: design conversation 2026-09-22. No PRD issue — this is an internal
> architecture change to the enrichment layer, not a new user-facing capability.

Split job enrichment into two kinds of work behind two interfaces: **typed
decisions** (bounded answers — scores and enums) which can be served by either
Claude or [Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev),
and **text enrichment** (prose and open-ended extraction) which only Claude can
serve. A config value selects the typed-decision implementation.

## Architectural decisions

Durable decisions that apply across all phases:

- **Two interfaces, not one.** `TypedDecisionProvider` (two implementations:
  Claude, Jev) and `TextEnrichmentProvider` (one implementation: Claude). The
  seam is *kind of work*, not *vendor* — Jev emits no strings, so a summary can
  never be served by it, and pretending otherwise with a single provider
  interface would force the Jev implementation to call Claude internally.
- **`TypedDecisionProvider` has exactly one method**, `decide(listing, profile)
  -> Decisions`, returning every typed field in one round trip. Jev batches all
  questions about a single `state` into one parallel call; TypeSafe reports
  batching 13 questions as 12.2x cheaper and 10x faster than asking serially. A
  per-field interface (`classify_remote_policy()`, `score_fit()`, …) would force
  N round trips and discard the entire advantage. One call also matches what
  Claude does today, keeping the two implementations comparable.
- **Policy lives in code, never in a prompt.** The current scoring prompt asks
  the model to both judge fit *and* apply the remote-work cap ("cap at 0.3
  max"). That conditional moves into `tools.py`. Without this the providers are
  not comparable, since only one of them can be given prose instructions.
- **`fit_score` stays a float in `[0.0, 1.0]`** regardless of provider. The fit
  rubric is **5 ordered levels** (no match → weak → plausible → strong →
  excellent), and Jev's `Score` returns a float in level-index space `[0, 4]`,
  normalized by dividing by 4. This preserves the `job_listings.fit_score`
  column, `FIT_SCORE_THRESHOLD`, the notifier, and the dashboard unchanged.
- **MCP tool signatures are frozen.** `analyze_job` and `score_job_fit` keep
  their current parameters and return shapes. `worker.py`, `notifier`,
  `dashboard`, and the DB schema are not touched. `enriched_json` only ever
  gains keys.
- **Jev model is pinned, not floating.** `JEV_MODEL` defaults to `jev-1.13.0`,
  not `jev-latest`. We branch on probability thresholds; an alias that moves
  underneath us silently changes routing behavior.
- **Provenance is recorded.** Every enrichment writes which provider and model
  produced it into `enriched_json`, so a score can always be attributed after
  the fact.
- **Config**: `ENRICHMENT_TYPED_PROVIDER` (`jev` | `claude`), `TYPESAFE_API_KEY`,
  `JEV_MODEL`. No knob for the text provider — a config value with one legal
  value is noise; add it if Jev ever generates strings.
- **Jev question inventory** (the bounded surface, all in one batched call):
  `fit` (Score, 5 levels), `experience_level` / `remote_policy` / `job_type` (Choice),
  and `requires_office_presence` / `requires_relocation` /
  `is_contract_or_freelance` (Noul). Output tokens are free, so additional
  questions are close to costless.
- **Claude keeps**: `skills`, `tech_stack`, `remote_flags`, `summary`.

### Known consequence: notification volume will shift

A 5-level normalized rubric does not distribute like Claude's freehand 0.0–1.0.
`FIT_SCORE_THRESHOLD=0.7` will not mean the same thing after the switch. Expect
to retune it (Phase 3 makes that evidence-based). Reverting is one env var.

### Jev constraints the implementation must respect

From TypeSafe's docs and published field reports:

- **Phrase questions positively.** Negations are read literally and misfire —
  `"The role is NOT remote"` is a bug. Ask the positive form, invert in Python.
- **No arithmetic, counting, or date ordering.** Any such logic stays in code.
- **Keep `state` tight.** Padding with irrelevant context *lowers* accuracy; Jev
  reads only what it is handed. Send title/company/location/description and the
  profile, nothing else.
- **Avoid high-cardinality `Choice`.** Ours are 3–5 options, well inside the
  safe range; Cribl measured 2–3x higher misclassification at 28 options, with
  known classes collapsing into `other`.
- **Include an explicit escape option** (`unknown` / `other`) so the model can
  decline rather than guess.
- **64k token request limit**, 32k for `state` plus the longest question. Long
  job descriptions must be truncated defensively.

---

## Phase 1: Provider seam, Claude behind it — no behavior change

**Needs no TypeSafe API key.** Completable today.

### What to build

Introduce `src/providers/` in the mcp-server: the two Protocols, the `Decisions`
and `TextEnrichment` dataclasses, and Claude implementations of both, built from
the prompts currently inlined in `tools.py`. Add a factory that reads
`ENRICHMENT_TYPED_PROVIDER`, accepting only `claude` in this phase.

Rewrite `tools.py` so it composes providers rather than owning prompts, and move
the remote-work cap out of the scoring prompt into Python. Replace the
`reasoning` string with one synthesized in code from the decision fields, so the
field is provider-independent from the start.

Fix two latent bugs in the process: `score_fit` currently returns
`{"score": 0.0}` on a `JSONDecodeError`, which makes a perfect match
indistinguishable from a rejected one and silently suppresses its Discord
notification; and `analyze_job_listing`'s `except` block references `response`,
which is unbound if `llm.complete` itself raises.

Claude still makes two API calls per listing, the same as today — but the split
changes from `analyze` + `score` to `typed decisions` + `text enrichment`. Call
count and therefore cost are unchanged; only the boundary moves.

Two things do change observably, both deliberately: `reasoning` becomes
synthesized rather than written by Claude, and a malformed response now surfaces
as an error instead of a silent 0.0 score. Everything else — scores, enums,
notification behavior — should be materially unchanged. This phase is otherwise
pure refactoring, which is what makes it a safe place to land the structure.

### Acceptance criteria

- [x] `TypedDecisionProvider` and `TextEnrichmentProvider` Protocols defined in `src/providers/base.py`
- [x] `Decisions` and `TextEnrichment` are frozen dataclasses with explicit field types
- [x] `ClaudeTypedDecisions` returns all typed fields from a single Claude call
- [x] `ClaudeTextEnrichment` returns `skills`, `tech_stack`, `remote_flags`, `summary`
- [x] `build_typed_provider()` accepts `claude` and raises a clear error on an unknown value
      — *deviation: `server.py` reads the env var and passes the name in, rather than
      the factory reading the environment itself. Keeps the factory testable.*
- [x] The remote-work cap is applied in Python, not in any prompt, and the "cap at 0.3 max" instruction is deleted from the prompt text
- [x] `reasoning` is synthesized in code from decision fields and cites the values that drove the cap
- [x] A malformed model response raises a typed error instead of returning `fit_score` 0.0
- [x] `analyze_job_listing` handles an exception raised by `llm.complete` without a `NameError`
- [x] `enriched_json` includes `provider` and `model` for every enrichment
- [x] MCP tool signatures for `analyze_job` and `score_job_fit` are byte-identical to before
- [x] Tests: provider protocol conformance via a fake, the cap applied at the boundary and just inside it, reasoning synthesis, malformed-response handling, and the existing `tests/test_tools.py` behavior preserved
- [ ] `make test-mcp-server` passes; `make up` enriches listings end-to-end as before
      — **NOT VERIFIED.** Docker is unreachable from this WSL distro (Docker Desktop
      WSL integration disabled), so the image test stage never ran. 27 tests pass in a
      venv built from the same requirements files, on Python 3.12 vs the image's 3.13.
      **Blocked regardless** by the pre-existing `mcp>=1.9.0` pin: mcp 2.x renamed
      `FastMCP` to `MCPServer`, so `src/server.py` fails to import on a fresh build.
      Needs `mcp>=1.9.0,<2` (or a 2.x migration) before `make up` can run at all.

---


### Emerged during implementation

- **Typed decisions no longer see the `location` field.** `analyze_job` passes
  `location` and `score_job_fit` does not, so keying the decision cache on it
  meant the two tools never shared an entry and the memoization silently did
  nothing — restoring the third call it exists to remove. Dropping `location`
  from the typed prompt is also the better judgment: the original prompt itself
  warned that listings are routinely tagged remote in `location` and then
  require office days, and the scraper already hard-filters on it. Remote-ness
  is now judged from the description alone. Pinned by
  `test_the_two_mcp_tool_shapes_share_one_cache_entry`.
- **`CachingTypedDecisions` was not in the original design.** It exists because
  the MCP surface exposes two tools that both need one provider round trip.
  Bounded LRU, keyed on the listing fields the provider actually sees plus the
  profile.
## Phase 2: Jev implementation behind the same interface

**Requires `TYPESAFE_API_KEY`.** Blocked until the key exists; everything else
in this phase can be written and unit-tested against a stubbed SDK client first.

### What to build

Add `typesafe-sdk` and implement `JevTypedDecisions` against
`AsyncTypeSafeClient`, mapping the question inventory above into one
`system_one()` call. Normalize the `Score` result into `[0.0, 1.0]`, carry
per-field confidence and raw probabilities through on `Decisions`, and truncate
oversized descriptions before sending.

Register `jev` in the factory and make it the default. Fail fast at startup with
an actionable message when the provider is `jev` and no key is present, rather
than failing per-listing at runtime.

Wire `TYPESAFE_API_KEY` and `JEV_MODEL` through `.env.example`,
`docker-compose.yaml`, `helm/envs/local/configmap.yaml` and `secret.yaml.example`.

### Acceptance criteria

- [x] `typesafe-sdk` pinned in `services/mcp-server/requirements.txt`
- [x] `JevTypedDecisions` issues exactly one `system_one()` call per listing
- [x] All questions are phrased positively; any inversion happens in Python
- [x] Every `Choice` includes an explicit `unknown`/`other` escape option
- [x] `Score` result is normalized to `[0.0, 1.0]` by `(levels - 1)` and clamped
- [x] `state` carries only title, company, description, and profile
      — *`location` deliberately excluded, per the phase 1 finding: it is the field
      the original prompt warned was unreliable, and omitting it keeps this
      provider's input identical across both MCP tools so the cache hits.*
- [x] Descriptions are truncated to stay within the 32k `state` budget
- [x] Per-field confidence and raw probabilities are persisted in `enriched_json`
- [x] `JEV_MODEL` defaults to the pinned `jev-1.13.0`, and the resolved model id is recorded per enrichment
- [x] `ENRICHMENT_TYPED_PROVIDER` defaults to `jev`
- [x] Startup fails with an actionable error when provider is `jev` and `TYPESAFE_API_KEY` is unset
- [x] Setting `ENRICHMENT_TYPED_PROVIDER=claude` fully reverts behavior with no code change
- [x] Config plumbed through `.env.example`, `docker-compose.yaml`, and `helm/envs/local/`
- [x] Tests: SDK response mapping against a stubbed client, score normalization including both endpoints, truncation, missing-key startup failure, and provider selection by config
- [ ] `make up` with a real key enriches listings end-to-end via Jev, and the dashboard shows scores
      — **NOT VERIFIED.** Needs a TYPESAFE_API_KEY, and Docker is still unreachable
      from this WSL distro. Everything below the network call is covered by tests
      built on the real SDK response models.

---


### What the real SDK turned out to be (typesafe-sdk 0.7.1)

The contained unknown flagged in the phase 1 design is resolved. Installing the
package and introspecting it beat both write-ups, which disagree with each other
*and* with the library:

- **`response.answers[...]` is correct.** The official docs page showing
  `response.choices[...]` / `response.nouls[...]` is wrong; the third-party
  practical guide had it right. `SystemOneResponse` is `(model, usage, answers)`.
- **`ScoreAnswer.probabilities` and `.legend` are `dict[int, ...]`, not arrays.**
  Every published example shows them as lists. Indexing a list where the library
  returns a dict would have failed only at runtime, against a live API.
- **`legend` carries the level descriptions**, so the normalization divisor is
  derived from the response rather than hardcoded to 4 — strictly better than
  what this plan originally specified.
- **`NoulAnswer` has no `confidence` field**; the probability is the confidence.
  Only `fit`, `experience_level`, `remote_policy` and `job_type` report one.
- **Answer models are frozen pydantic instances** — tests must build responses,
  not mutate them.
- `AsyncTypeSafeClient(api_key=..., model=...)`, and `system_one()` takes `model`
  per call, which is what the pinning requires.

### Other decisions made here

- **`typesafe-sdk>=0.7.1,<1`** — upper bound deliberate. A pre-1.0 dependency
  with no ceiling is what just broke `mcp` in this same file.
- **The `TYPESAFE_API_KEY` secretKeyRef is `optional: true`.** Without it,
  selecting the claude provider wedges the pod in `CreateContainerConfigError`
  before the app can explain itself. Optional lets it start and hit the
  application's own fail-fast, which names the variable and the way to revert.
- **Claude is still required even when the provider is `jev`** — text enrichment
  has no second implementation, so `ANTHROPIC_API_KEY` stays mandatory.
## Phase 3: Comparison harness and evidence-based threshold retune

### What to build

A `make compare` target that replays listings already stored in Postgres through
both providers and reports agreement, per-field divergence, latency, and cost.
The point of Phase 3 is to answer the question that motivated the whole change —
*does Jev agree with Claude on my data?* — with evidence rather than impression,
and to retune `FIT_SCORE_THRESHOLD` against a real distribution instead of a
guess.

Surface `provider`, `model`, and confidence in the dashboard detail view so a
low-confidence score is visible rather than silently trusted.

### Acceptance criteria

- [ ] `make compare` replays stored listings through both providers without mutating rows
- [ ] Report includes score correlation, mean absolute difference, and per-enum agreement rate
- [ ] Report includes measured p50/p95 latency and token cost per provider
- [ ] Listings where the two providers disagree past a configurable margin are listed for manual inspection
- [ ] `FIT_SCORE_THRESHOLD` is retuned from the observed Jev distribution and the chosen value is recorded here with its rationale
- [ ] Dashboard detail view shows provider, model, and fit confidence
- [ ] Tests: report arithmetic against a fixed fixture set

---

## Out of scope

- Changes to `scraper`, `notifier`, `dashboard` beyond the Phase 3 detail view
- Database schema changes — everything new rides in the existing `enriched_json` JSONB column
- Replacing Claude for text enrichment, which Jev cannot do by construction
- Upgrading the pinned `claude-sonnet-4-20250514` model in `llm.py` — worth doing, tracked separately so it does not confound the comparison

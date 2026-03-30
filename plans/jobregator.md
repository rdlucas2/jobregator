# Plan: Jobregator — Personal Job Listing Aggregator

> Source PRD: https://github.com/rdlucas2/jobregator/issues/2

## Architectural decisions

Durable decisions that apply across all phases:

- **Services**: 5 services (Go Scraper, Python Enrichment Worker, Python MCP Enrichment Server, Python Discord Notifier, TypeScript Web Dashboard), 3 languages
- **Schema**: `job_listings` table with unique constraint on `(source, external_id)`, `jsonb` column for AI analysis, fit score as float (0.0–1.0)
- **Key models**: `RawListing` (Go → NATS), `EnrichedListing` (Python → Postgres), `SearchProfile` (YAML)
- **NATS subjects**: `jobs.raw` (scraper → enrichment worker), `jobs.enriched` (enrichment worker → discord notifier)
- **MCP tools**: `analyze_job_listing` (extract structured data), `score_fit` (relevance score + reasoning)
- **Dashboard routes**: `GET /` (listing table), `GET /listings/:id` (detail view), `GET /listings` (htmx filtered/paginated fragments)
- **Config**: Single YAML profile file (`profile.yaml`) with `search_terms`, `hard_filters`, `profile` sections — single source of truth
- **Message broker**: NATS with JetStream (durable consumers)
- **Database**: PostgreSQL
- **Container registry**: ghcr.io/rdlucas2
- **Local dev**: Docker Compose
- **Production**: Docker Desktop K8s + ArgoCD (App of Apps)

---

## Phase 1: Go Scraper → NATS → Postgres Skeleton + Docker Compose

**User stories**: 1, 8, 9, 12, 15, 17

### What to build

A thin end-to-end pipeline: Go scraper reads search terms from a YAML profile, queries the Adzuna API, normalizes results into `RawListing` structs, and publishes them to NATS `jobs.raw`. A minimal Python worker subscribes to `jobs.raw` and writes raw listings into a Postgres `job_listings` table.

The Go scraper uses a `JobSource` adapter interface so new sources can be added later by implementing the interface. Only the Adzuna adapter is built in this phase.

Docker Compose orchestrates all infrastructure (NATS, Postgres) and both services. Multi-stage Dockerfiles (base → test → artifact) for each service from the start.

Time-window filtering (14h lookback) is included in the scraper to avoid re-fetching old listings on repeated runs.

### Acceptance criteria

- [ ] YAML profile with `search_terms` is parsed by the Go scraper at startup
- [ ] Go scraper defines a `JobSource` interface and implements it for Adzuna
- [ ] Scraper queries Adzuna API and publishes normalized `RawListing` messages to NATS `jobs.raw`
- [ ] Scraper applies a configurable time-window filter (default 14h lookback)
- [ ] Python worker subscribes to NATS `jobs.raw` via JetStream durable consumer
- [ ] Python worker writes raw listings to Postgres `job_listings` table
- [ ] Postgres has a unique constraint on `(source, external_id)`
- [ ] Docker Compose brings up NATS, Postgres, scraper, and worker
- [ ] Multi-stage Dockerfiles for both Go scraper and Python worker
- [ ] Running `docker compose up` demonstrates data flowing from Adzuna → NATS → Postgres
- [ ] Tests exist for: Go adapter interface, Adzuna response mapping, YAML profile parsing, time-window filter logic

---

## Phase 2: MCP Enrichment Server + Worker Integration

**User stories**: 3, 7, 14, 16, 19, 20

### What to build

Build the Python MCP Enrichment Server using the Python MCP SDK. It exposes two tools: `analyze_job_listing` (extracts structured data like skills, experience level, remote policy, tech stack) and `score_fit` (scores a listing against the user's natural language profile on a 0.0–1.0 scale with reasoning). Both tools wrap the Claude API via the Anthropic Python SDK. The server reads the `profile` section of the YAML config for scoring context.

Upgrade the Phase 1 Python worker into a full MCP client. Before calling the MCP server, the worker checks Postgres for an existing `(source, external_id)` to avoid duplicate LLM calls. After enrichment, the worker writes the enriched listing (structured analysis as `jsonb`, fit score) back to Postgres and publishes to NATS `jobs.enriched`.

Add both services to Docker Compose.

### Acceptance criteria

- [ ] MCP Enrichment Server starts and registers tools via MCP protocol
- [ ] `analyze_job_listing` tool accepts a raw listing and returns structured analysis
- [ ] `score_fit` tool accepts a raw listing and returns a fit score (0.0–1.0) with reasoning
- [ ] Both tools call the Claude API via the Anthropic SDK
- [ ] MCP server reads the natural language `profile` from the YAML config
- [ ] Enrichment worker connects to MCP server as an MCP client
- [ ] Enrichment worker checks Postgres for duplicates before calling MCP server
- [ ] Enrichment worker writes enriched listings (jsonb analysis, fit score) to Postgres
- [ ] Enrichment worker publishes enriched listings to NATS `jobs.enriched`
- [ ] Both services added to Docker Compose
- [ ] Tests exist for: MCP tool handlers (mocked Claude API), dedup logic, enrichment worker flow

---

## Phase 3: Discord Notifier

**User stories**: 4

### What to build

A small Python service that subscribes to NATS `jobs.enriched` via a JetStream durable consumer. For each enriched listing, it checks the fit score against a configurable threshold. If the score meets or exceeds the threshold, it sends a Discord message via webhook containing the job title, company, fit score, and a link to the original listing.

Add to Docker Compose.

### Acceptance criteria

- [ ] Discord notifier subscribes to NATS `jobs.enriched` via JetStream durable consumer
- [ ] Fit score threshold is configurable via environment variable
- [ ] Listings meeting the threshold trigger a Discord webhook POST
- [ ] Discord message includes job title, company, fit score, and source URL
- [ ] Listings below the threshold are acknowledged and skipped
- [ ] Service added to Docker Compose
- [ ] Tests exist for: threshold filtering logic, webhook payload formatting

---

## Phase 4: Web Dashboard (Hono + htmx)

**User stories**: 5, 6, 22

### What to build

A TypeScript web dashboard using Hono as the server framework, rendering raw HTML/CSS with htmx for interactivity. The server reads from Postgres and serves:

- A main listing table at `GET /` showing all enriched job listings (title, company, score, source, date)
- Filtered/paginated HTML fragments at `GET /listings` for htmx to swap in (filter by score range, source, keyword search)
- A detail view at `GET /listings/:id` showing the full listing with AI analysis breakdown (extracted skills, fit score reasoning)

No frontend build step. Raw HTML/CSS served by Hono with htmx attributes for dynamic behavior.

Add to Docker Compose.

### Acceptance criteria

- [ ] Hono server starts and connects to Postgres
- [ ] `GET /` renders a full HTML page with a listing table and filter controls
- [ ] `GET /listings` returns HTML fragments for htmx (filtered, paginated)
- [ ] `GET /listings/:id` renders a detail page with AI scoring breakdown
- [ ] Filtering by score range, source, and keyword search works via htmx
- [ ] Raw HTML/CSS with no frontend build step
- [ ] Service added to Docker Compose
- [ ] Tests exist for: route handlers returning correct HTML given mock Postgres data

---

## Phase 5: Hard Filters + Time-Window Tuning

**User stories**: 2, 9

### What to build

Enhance the Go scraper to apply `hard_filters` from the YAML profile before publishing to NATS. Filters include: remote-only, country allowlist, minimum salary, and excluded title keywords. Listings that fail any hard filter are dropped before reaching NATS.

Make the time-window lookback hours configurable via environment variable (default 14h) so it can be tuned independently of the cron schedule.

### Acceptance criteria

- [ ] Scraper reads `hard_filters` from YAML profile
- [ ] Listings not matching `remote: true` are filtered out (when configured)
- [ ] Listings outside allowed `countries` are filtered out
- [ ] Listings below `min_salary` are filtered out (when salary data is available)
- [ ] Listings matching `exclude_titles` keywords are filtered out
- [ ] Time-window lookback is configurable via `LOOKBACK_HOURS` env var (default 14)
- [ ] Tests exist for: each hard filter rule, edge cases (missing salary data, partial title matches)

---

## Phase 6: Kubernetes + ArgoCD Deployment

**User stories**: 10, 11, 18

### What to build

Helm charts for all services, following the patterns from rdlucas2/ddargo: a reusable `web-chart` (for the Hono dashboard) and `job-chart` (for the Go scraper CronJob). Long-running Python services (enrichment worker, MCP server, discord notifier) use `web-chart` as Deployments.

ArgoCD App of Apps bootstrap chart that templates Application resources for all services. CronJob schedule set to every 12 hours.

GitHub Actions CI pipelines for each service: build, test, security scan (gitleaks, Trivy), push to ghcr.io/rdlucas2.

### Acceptance criteria

- [ ] Helm `web-chart` deploys the Hono dashboard, enrichment worker, MCP server, and discord notifier
- [ ] Helm `job-chart` deploys the Go scraper as a CronJob (every 12h)
- [ ] Environment-specific values files for local Docker Desktop K8s
- [ ] ArgoCD App of Apps bootstrap chart templates all service Applications
- [ ] ArgoCD auto-syncs with prune and self-heal enabled
- [ ] NATS and Postgres deployed via Helm charts (e.g., bitnami/nats, bitnami/postgresql)
- [ ] GitHub Actions workflows build, test, scan, and push images for each service
- [ ] `kubectl` and ArgoCD show all services running on Docker Desktop K8s

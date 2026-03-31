# Jobregator

> A personal job listing aggregator that scrapes postings, enriches them with AI-powered relevance scoring, and delivers high-scoring matches via Discord and a web dashboard.

## Architecture

```
Adzuna API ─→ Go Scraper ─→ NATS (jobs.raw) ─→ Python Worker ─→ Postgres
                                                     │
                                              MCP Server (Claude API)
                                                     │
                                              NATS (jobs.enriched)
                                               ┌─────┴─────┐
                                         Discord Notifier   Dashboard (SSE)
```

Five services, three languages:

| Service | Language | Description |
|---------|----------|-------------|
| **scraper** | Go | Fetches listings from Adzuna API, applies hard filters (remote, salary, country, title keywords, description-based remote validation), publishes to NATS |
| **worker** | Python | MCP client that deduplicates, enriches via Claude API, writes to Postgres, publishes enriched listings |
| **mcp-server** | Python | MCP server exposing `analyze_job` and `score_job_fit` tools wrapping the Claude API |
| **notifier** | Python | Subscribes to enriched listings, sends Discord webhook for high-scoring matches |
| **dashboard** | TypeScript | Hono + htmx web UI with filtering, sorting, charts, and SSE live updates |

## Quick Start

### Prerequisites

- [Docker](https://www.docker.com/) and Docker Compose
- [make](https://www.gnu.org/software/make/)

### Setup

```bash
# Clone and configure
git clone https://github.com/rdlucas2/jobregator.git
cd jobregator
cp .env.example .env
# Edit .env with your API keys (Adzuna, Anthropic, Discord webhook)

# Install git hooks (gitleaks pre-commit secret scanning)
make install-hooks

# Start everything
make up
```

The dashboard is available at [http://localhost:3000](http://localhost:3000).

### Environment Variables

See `.env.example` for all required variables. Key ones:

| Variable | Description |
|----------|-------------|
| `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` | Adzuna API credentials |
| `ANTHROPIC_API_KEY` | Claude API key for job enrichment |
| `DISCORD_WEBHOOK_URL` | Discord channel webhook for notifications |
| `ENABLE_ENRICHMENT` | Toggle AI enrichment on/off (`true`/`false`) |
| `FIT_SCORE_THRESHOLD` | Minimum score to trigger Discord notification (default `0.7`) |
| `LOOKBACK_HOURS` | How far back to fetch listings (default `14`) |

## Repository Structure

```
jobregator/
├── services/
│   ├── scraper/          # Go — Adzuna adapter, NATS publisher, hard filters
│   ├── worker/           # Python — MCP client, dedup, Postgres writer
│   ├── mcp-server/       # Python — Claude API enrichment tools
│   ├── notifier/         # Python — Discord webhook notifications
│   └── dashboard/        # TypeScript — Hono + htmx web UI
├── config/
│   └── profile.yaml      # Search terms, hard filters, candidate profile
├── helm/
│   ├── web-chart/        # Generic Deployment/Service/Ingress chart
│   ├── job-chart/        # Generic CronJob chart
│   └── envs/             # Per-environment values (common/, local/)
├── argo/
│   └── bootstrap-local/  # ArgoCD App of Apps for Docker Desktop K8s
├── .github/workflows/    # Per-service CI: build → test → scan → push
├── docker-compose.yaml   # Local development orchestration
└── Makefile              # Build, test, and utility targets
```

## Makefile Reference

```bash
make help              # Show all targets
make up                # Start all services (docker compose up -d --build)
make down              # Stop all services
make logs              # Tail logs

make build-scraper     # Build a single service image
make test-dashboard    # Run tests for a single service
make build             # Build all service images
make test              # Run all service tests

make trivy-scan-scraper  # CVE scan a service image
make gitleaks-scan       # Scan repo for secrets
```

## Configuration

The scraper is configured via `config/profile.yaml`:

```yaml
search_terms:
  - "DevOps Engineer"
  - "Platform Engineer"
hard_filters:
  remote: true
  countries: ["US"]
  min_salary: 150000
  exclude_titles: ["Junior", "Intern"]
profile: |
  Senior DevOps / Platform Engineer with 10+ years experience...
```

The `profile` field is sent to the Claude API for relevance scoring. Hard filters are applied at the scraper level before any API calls.

## Deployment

### Docker Compose (local development)

```bash
make up
```

### Kubernetes + ArgoCD

For Docker Desktop K8s with ArgoCD:

```bash
# Apply ConfigMap and Secret
kubectl apply -f helm/envs/local/configmap.yaml
# Create secret.yaml from secret.yaml.example, fill in values, then:
kubectl apply -f helm/envs/local/secret.yaml

# Bootstrap ArgoCD App of Apps
helm install bootstrap argo/bootstrap-local
```

ArgoCD will auto-sync all services with prune and self-heal enabled.

## CI/CD

GitHub Actions workflows in `.github/workflows/` trigger on path-based changes per service:

1. Build multi-stage Docker image
2. Run tests (target: `test`)
3. Trivy security scan (CRITICAL + HIGH)
4. Push to `ghcr.io/rdlucas2` (main branch and tags only)

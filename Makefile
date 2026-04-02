# =============================================================================
# jobregator — Makefile
# Usage: make help
# =============================================================================

REGISTRY ?= ghcr.io/rdlucas2
IMAGE_TAG ?= latest

SERVICES = scraper worker dashboard notifier mcp-server

# Load .env if present (never commit .env — see .env.example)
ifneq (,$(wildcard .env))
  include .env
  export
endif

.PHONY: help build test up down logs \
        build-% test-% \
        install-hooks gitleaks-scan trivy-scan-%

.DEFAULT_GOAL := help

help: ## Show available targets
	@grep -E '^[a-zA-Z_%-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}'

# — Docker Compose ————————————————————————————————————————————————————————————

up: ## Start all services via Docker Compose
	docker compose up -d --build

down: ## Stop all services
	docker compose down

logs: ## Tail logs for all services
	docker compose logs -f

# — Per-Service Build & Test ——————————————————————————————————————————————————

build-%: ## Build a service artifact image (e.g. make build-scraper)
	@if [ "$*" = "worker" ]; then \
	  docker build --target artifact -t jobregator-$*:$(IMAGE_TAG) -f services/worker/Dockerfile . ; \
	else \
	  docker build --target artifact -t jobregator-$*:$(IMAGE_TAG) services/$* ; \
	fi

test-%: ## Run tests for a service (e.g. make test-dashboard)
	@if [ "$*" = "worker" ]; then \
	  docker build --target test -t jobregator-$*-test:$(IMAGE_TAG) -f services/worker/Dockerfile . && \
	  docker run --rm jobregator-$*-test:$(IMAGE_TAG) ; \
	else \
	  docker build --target test -t jobregator-$*-test:$(IMAGE_TAG) services/$* && \
	  docker run --rm jobregator-$*-test:$(IMAGE_TAG) ; \
	fi

build: $(addprefix build-,$(SERVICES)) ## Build all service images

test: $(addprefix test-,$(SERVICES)) ## Run tests for all services

# — Git Hooks —————————————————————————————————————————————————————————————————

install-hooks: ## Install git hooks from .githooks/ (run once after cloning)
	git config core.hooksPath .githooks
	chmod +x .githooks/pre-commit
	@echo "  Git hooks installed. pre-commit will scan for secrets via gitleaks."

gitleaks-scan: ## Scan entire repo history for secrets with gitleaks
	docker run --rm \
	  -v "$(PWD):/repo" \
	  -w /repo \
	  ghcr.io/gitleaks/gitleaks:v8.21.2 \
	  detect --no-banner -v

# — CVE Scanning ——————————————————————————————————————————————————————————————

trivy-scan-%: build-% ## Scan a service image for CVEs (e.g. make trivy-scan-dashboard)
	docker run --rm \
	  -v /var/run/docker.sock:/var/run/docker.sock \
	  aquasec/trivy image \
	    --format table \
	    --scanners vuln \
	    jobregator-$*:$(IMAGE_TAG)

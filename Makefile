# =============================================================================
# jobregator — Makefile
# Usage: make help
# =============================================================================

APP_NAME  ?= jobregator
IMAGE_TAG ?= latest
PORT      ?= 8080
REGISTRY  ?= ghcr.io/rdlucas2

# Load .env if present (never commit .env — see .env.example)
ifneq (,$(wildcard .env))
  include .env
  export
endif

.PHONY: help build build-test test package run debug debug-test \
        install-hooks gitleaks-scan \
        sonar-start sonar-scan trivy-scan

# Default target
.DEFAULT_GOAL := help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# — Build ——————————————————————————————————————————————————————————————————————

build: ## Build the artifact image
	docker build -t $(APP_NAME):$(IMAGE_TAG) .

build-test: ## Build the test image (targets the test stage)
	docker build -t $(APP_NAME)-test:$(IMAGE_TAG) . --target test

# — Test ———————————————————————————————————————————————————————————————————————

test: build-test ## Run tests and write coverage reports to ./coverage/
	@mkdir -p coverage
	docker run --rm -v $(PWD)/coverage:/out $(APP_NAME)-test:$(IMAGE_TAG)

# — Package ————————————————————————————————————————————————————————————————————

package: build ## Tag and push artifact image to registry (requires REGISTRY)
	docker tag $(APP_NAME):$(IMAGE_TAG) $(REGISTRY)/$(APP_NAME):$(IMAGE_TAG)
	docker push $(REGISTRY)/$(APP_NAME):$(IMAGE_TAG)

# — Run / Debug ————————————————————————————————————————————————————————————————

run: build ## Run the artifact container (loads .env)
	docker run --rm --env-file .env -p $(PORT):$(PORT) $(APP_NAME):$(IMAGE_TAG)

debug: build ## Open a shell in the artifact container
	docker run -it --rm --env-file .env --entrypoint /bin/sh $(APP_NAME):$(IMAGE_TAG)

debug-test: build-test ## Open a shell in the test container
	docker run -it --rm --entrypoint /bin/sh $(APP_NAME)-test:$(IMAGE_TAG)

# — Git Hooks —————————————————————————————————————————————————————————————————

install-hooks: ## Install git hooks from .githooks/ (run once after cloning)
	git config core.hooksPath .githooks
	chmod +x .githooks/pre-commit
	@echo "  Git hooks installed. pre-commit will scan for secrets via gitleaks."

gitleaks-scan: ## Scan entire repo history for secrets with gitleaks (Docker)
	docker run --rm \
	  -v "$(PWD):/repo" \
	  -w /repo \
	  ghcr.io/gitleaks/gitleaks:v8.21.2 \
	  detect --no-banner -v

# — Static Analysis & CVE Scanning —————————————————————————————————————————————

sonar-start: ## Start local SonarQube at http://localhost:9000 (admin/admin)
	docker run -d --name sonarqube -p 9000:9000 sonarqube
	@echo ""
	@echo "  SonarQube starting — monitor with: docker logs -f sonarqube"
	@echo "  When ready: browse http://localhost:9000 and generate a token."
	@echo "  Then set SONAR_TOKEN in .env and run: make sonar-scan"

sonar-scan: ## Run SonarQube static analysis (requires SONAR_TOKEN in .env)
	docker run -it --rm \
	  -e SONAR_HOST_URL="http://host.docker.internal:9000" \
	  -e SONAR_TOKEN="$(SONAR_TOKEN)" \
	  -v "$(PWD):/usr/src" \
	  sonarsource/sonar-scanner-cli

trivy-scan: build ## Scan artifact image for CVEs with Trivy (table + JSON)
	@mkdir -p .
	docker run --rm \
	  -v /var/run/docker.sock:/var/run/docker.sock \
	  -v "$(PWD):/output" \
	  aquasec/trivy image \
	    --format table \
	    --output /output/trivy-report.txt \
	    --scanners vuln \
	    $(APP_NAME):$(IMAGE_TAG)
	docker run --rm \
	  -v /var/run/docker.sock:/var/run/docker.sock \
	  -v "$(PWD):/output" \
	  aquasec/trivy image \
	    --format json \
	    --output /output/trivy-report.json \
	    --scanners vuln \
	    $(APP_NAME):$(IMAGE_TAG)
	@echo ""
	@echo "  Trivy reports written to trivy-report.txt and trivy-report.json"

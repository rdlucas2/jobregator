# [app-name]

> Replace this line with a one-sentence description of what your application does.

This repository is a **GitHub template** providing a language-agnostic project scaffold with:

- Multi-stage Docker build (base → test → artifact)
- Makefile with build, test, package, debug, static analysis, and CVE scanning targets
- Pre-commit secret scanning via [gitleaks](https://github.com/gitleaks/gitleaks)
- `.env`-based local configuration (never committed)
- A curated set of Claude Code skills for AI-assisted development

---

## Getting Started

### 1. Use this template

Click **Use this template** on GitHub, or clone directly:

```bash
git clone https://github.com/<your-org>/<your-repo>.git
cd <your-repo>
```

### 2. Set up your environment

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

Edit `.env` — see [Environment Variables](#environment-variables) for what each value does.

### 3. Install git hooks

Run once after cloning to enable the gitleaks pre-commit secret scan:

```bash
make install-hooks
```

This sets `core.hooksPath = .githooks` in your local git config. From this point, every `git commit` will scan staged files for secrets before allowing the commit through.

### 4. Verify everything works

```bash
make help      # list all available targets
make build     # build the artifact image
make test      # run tests (writes coverage to ./coverage/)
```

---

## Makefile Reference

Run `make help` at any time to see all targets and descriptions.

```
make help
```

### Build

| Target | Description |
|---|---|
| `make build` | Build the production artifact image |
| `make build-test` | Build the test image (targets the `test` stage) |

### Test

| Target | Description |
|---|---|
| `make test` | Run tests inside the test container; writes coverage reports to `./coverage/` |

### Package

| Target | Description |
|---|---|
| `make package` | Tag and push the artifact image to `REGISTRY` |

### Run & Debug Locally

| Target | Description |
|---|---|
| `make run` | Run the artifact container, loading `.env` and binding `PORT` |
| `make debug` | Open an interactive shell in the artifact container |
| `make debug-test` | Open an interactive shell in the test container |

### Static Analysis & CVE Scanning

| Target | Description |
|---|---|
| `make sonar-start` | Start a local SonarQube instance at [http://localhost:9000](http://localhost:9000) |
| `make sonar-scan` | Run SonarQube static analysis (requires `SONAR_TOKEN` in `.env`) |
| `make trivy-scan` | Scan the artifact image for CVEs; writes `trivy-report.txt` and `trivy-report.json` |

### Git Hooks

| Target | Description |
|---|---|
| `make install-hooks` | Configure git to use `.githooks/` (run once after cloning) |
| `make gitleaks-scan` | Scan the full repository history for secrets on demand |

---

## Working Locally

### Building the application

```bash
make build
```

Builds the `artifact` stage of the Dockerfile and tags it `<APP_NAME>:<IMAGE_TAG>`.

To override defaults without editing `.env`:

```bash
make build APP_NAME=myapp IMAGE_TAG=v1.2.3
```

### Running tests

```bash
make test
```

Builds the `test` stage and runs it. Coverage reports are written to `./coverage/` on your host (mounted as `/out` inside the container).

To inspect the test environment interactively:

```bash
make debug-test
```

### Packaging and pushing

Ensure `REGISTRY` is set in `.env` (e.g. `ghcr.io/your-org`), then:

```bash
make package
```

This tags the locally-built image and pushes it to your registry.

### Running the application

```bash
make run
```

Runs the artifact container with your `.env` values injected and `PORT` bound on the host. To get a shell inside the running artifact image instead:

```bash
make debug
```

### Scanning for CVEs

```bash
make trivy-scan
```

Produces `trivy-report.txt` (human-readable table) and `trivy-report.json` in the project root. Both are git-ignored.

### Static code analysis with SonarQube

```bash
# 1. Start SonarQube (first time only, or after `docker rm sonarqube`)
make sonar-start

# 2. Monitor startup
docker logs -f sonarqube

# 3. Browse http://localhost:9000 (admin / admin), generate a token, add it to .env:
#    SONAR_TOKEN=<your-token>

# 4. Run the scan
make sonar-scan
```

---

## Environment Variables

Copy `.env.example` to `.env` and update these values:

| Variable | Description | Example |
|---|---|---|
| `APP_NAME` | Docker image name | `myapp` |
| `IMAGE_TAG` | Docker image tag | `latest` or `v1.0.0` |
| `PORT` | Port the application listens on | `8080` |
| `REGISTRY` | Container registry prefix for `make package` | `ghcr.io/your-org` |
| `SONAR_TOKEN` | SonarQube authentication token for `make sonar-scan` | *(generate at localhost:9000)* |

`.env` is git-ignored and docker-ignored. **Never commit it.**

---

## Updating the Placeholders

When you start building your actual application, work through the following checklist.

### `Dockerfile`

The Dockerfile has three stages, each with `TODO` comments guiding what to fill in:

**Stage 1 — `base`** (production build)
- [ ] Replace `FROM alpine:3.21.3` with your language's builder image (e.g. `golang:1.23.4-alpine`, `node:22.12.0-alpine`, `python:3.13.1-slim`) — keep the version pinned
- [ ] Copy your dependency manifest first (e.g. `go.mod`/`go.sum`, `package.json`/`package-lock.json`, `requirements.txt`) and install dependencies before copying source — this preserves the cache layer
- [ ] Copy source and add the build command for your language
- [ ] Remove the placeholder `RUN echo "base layer placeholder"` line

**Stage 2 — `test`** (test runner)
- [ ] Install your test runner / coverage tool (e.g. `gotestsum`, `jest`, `pytest`)
- [ ] Replace the placeholder `ENTRYPOINT` with your test command, writing results to `/out/` so `make test` can retrieve them from the host mount

**Stage 3 — `artifact`** (distributable)
- [ ] Add `COPY --from=base` lines for your compiled binary and any required static assets
- [ ] Update `EXPOSE` to match your actual application port
- [ ] Replace the placeholder `ENTRYPOINT` with your real startup command

### `Makefile`

- [ ] Update `APP_NAME` default (currently `jobregator`) to your project name
- [ ] Update `PORT` default if your application uses a different port
- [ ] Update `REGISTRY` default to your container registry

### `.env.example`

- [ ] Update `APP_NAME`, `PORT`, and `REGISTRY` to match your project defaults
- [ ] Add any application-specific environment variables your app needs (database URLs, API keys, feature flags, etc.) with placeholder/example values

### `CLAUDE.md`

- [ ] The ground rules are project-agnostic and can stay as-is
- [ ] Add any project-specific conventions, naming rules, or instructions for the AI assistant relevant to your application

### Skills

The `.claude/skills/` directory contains a curated set of AI assistant skills. Review and remove any that aren't relevant to your stack:

| Skill | Keep if... |
|---|---|
| `accessibility` | You're building a web UI |
| `code-review` | Always useful |
| `conventional-commits` | Always — enforced by ground rules |
| `design-an-interface` | You're designing APIs or modules |
| `docker-best-practices` | Always — you have a Dockerfile |
| `makefile-best-practices` | Always — you have a Makefile |
| `twelve-factor` | You're building cloud-native / containerised apps |
| `tdd` | You're doing test-driven development |
| `triage-issue` | You're using GitHub Issues |
| `prd-to-issues` / `prd-to-plan` | You're writing PRDs |
| `qa` | You want conversational bug filing |

---

## Prerequisites

- [Docker](https://www.docker.com/) — required for all build, test, and scan targets
- [make](https://www.gnu.org/software/make/) — available by default on macOS and Linux; Windows users can use WSL or [GnuWin32](http://gnuwin32.sourceforge.net/packages/make.htm)
- [gitleaks](https://github.com/gitleaks/gitleaks#installing) *(optional)* — used by the pre-commit hook; Docker is used as a fallback if not installed locally

---

## License

[MIT](LICENSE) — or replace with your preferred license.

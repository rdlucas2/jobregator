# syntax=docker/dockerfile:1

# =============================================================================
# Stage 1: base — install dependencies for worker + MCP server
# =============================================================================
FROM python:3.13-slim AS base

WORKDIR /app

# Install all Python dependencies (worker + MCP server)
COPY services/worker/requirements.txt ./requirements.txt
COPY services/mcp-server/requirements.txt ./mcp-requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r mcp-requirements.txt

# Copy worker source
COPY services/worker/src/ ./src/

# Copy MCP server source (worker spawns it via stdio)
COPY services/mcp-server/src/ /mcp-server/src/

# =============================================================================
# Stage 2: test — run worker tests only
# =============================================================================
FROM base AS test

COPY services/worker/requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY services/worker/tests/ ./tests/

RUN mkdir -p /out
ENTRYPOINT ["pytest", "-v", "--tb=short", "tests/"]

# =============================================================================
# Stage 3: artifact — minimal production image
# =============================================================================
FROM python:3.13-slim AS artifact

RUN addgroup --system nonroot && \
    adduser --system --ingroup nonroot nonroot

WORKDIR /home/nonroot

COPY --from=base /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=base /app/src ./src/
COPY --from=base /mcp-server/src/ /mcp-server/src/

ENV HOME=/home/nonroot
RUN chown -R nonroot:nonroot $HOME && \
    chown -R nonroot:nonroot /tmp && \
    chown -R nonroot:nonroot /mcp-server

USER nonroot

ENTRYPOINT ["python", "-m", "src.worker"]

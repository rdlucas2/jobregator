# syntax=docker/dockerfile:1

# =============================================================================
# Stage 1: base — install dependencies
# =============================================================================
FROM python:3.13-slim AS base

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

# =============================================================================
# Stage 2: test — run tests with coverage
# =============================================================================
FROM base AS test

COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY tests/ ./tests/

RUN mkdir -p /out
ENTRYPOINT ["pytest", "-v", "--tb=short", "tests/"]

# =============================================================================
# Stage 3: artifact — minimal production image
# =============================================================================
FROM python:3.13-slim AS artifact

RUN rm -f /sbin/apk && \
    rm -rf /etc/apk /lib/apk /usr/share/apk /var/lib/apk

RUN addgroup --system nonroot && \
    adduser --system --ingroup nonroot nonroot

WORKDIR /home/nonroot

COPY --from=base /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=base /app/src ./src/

ENV HOME=/home/nonroot
RUN chown -R nonroot:nonroot $HOME && \
    chown -R nonroot:nonroot /tmp

USER nonroot

ENTRYPOINT ["python", "-m", "src.worker"]

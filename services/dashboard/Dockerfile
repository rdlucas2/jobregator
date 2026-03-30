# syntax=docker/dockerfile:1

# =============================================================================
# Stage 1: base — install dependencies and build
# =============================================================================
FROM node:22-alpine AS base

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY tsconfig.json ./
COPY src/ ./src/

# =============================================================================
# Stage 2: test — run vitest
# =============================================================================
FROM base AS test

ENTRYPOINT ["npx", "vitest", "run"]

# =============================================================================
# Stage 3: artifact — minimal production image
# =============================================================================
FROM node:22-alpine AS artifact

RUN addgroup --system nonroot && \
    adduser --system --ingroup nonroot nonroot

WORKDIR /home/nonroot/app

COPY --from=base /app/node_modules ./node_modules
COPY --from=base /app/package.json ./
COPY --from=base /app/tsconfig.json ./
COPY --from=base /app/src ./src

ENV HOME=/home/nonroot
RUN chown -R nonroot:nonroot /home/nonroot

USER nonroot

EXPOSE 3000
ENTRYPOINT ["npx", "tsx", "src/index.ts"]

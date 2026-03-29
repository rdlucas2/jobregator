# syntax=docker/dockerfile:1

# =============================================================================
# Stage 1: base — build the Go binary
# =============================================================================
FROM golang:1.25-alpine AS base

WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 go build -o scraper ./cmd/scraper

# =============================================================================
# Stage 2: test — run tests with coverage
# =============================================================================
FROM base AS test

RUN mkdir -p /out
ENTRYPOINT ["go", "test", "-coverprofile=/out/coverage.out", "-v", "./..."]

# =============================================================================
# Stage 3: artifact — minimal production image
# =============================================================================
FROM alpine:3.21.3 AS artifact

RUN rm -f /sbin/apk && \
    rm -rf /etc/apk /lib/apk /usr/share/apk /var/lib/apk

RUN addgroup --system nonroot && \
    adduser --system --ingroup nonroot nonroot

COPY --from=base /app/scraper /home/nonroot/scraper

ENV HOME=/home/nonroot
RUN chown -R nonroot:nonroot $HOME && \
    chown -R nonroot:nonroot /tmp

USER nonroot
WORKDIR /home/nonroot

ENTRYPOINT ["./scraper"]

# syntax=docker/dockerfile:1

# =============================================================================
# Stage 1: base
# Installs production dependencies and builds the application.
# TODO: Replace the alpine base with the appropriate language builder image
#       (e.g. golang:1.23.4-alpine, node:22.12.0-alpine, python:3.13.1-slim)
#       and add dependency installation + build steps for your language.
# =============================================================================
FROM alpine:3.21.3 AS base

WORKDIR /app

# TODO: Install production dependencies, e.g.:
#   COPY go.mod go.sum ./
#   RUN go mod download
#   COPY ./src ./src
#   RUN go build -o myapp ./src

# Placeholder — remove once real build steps are added
RUN echo "base layer placeholder" > /app/.build-marker

# =============================================================================
# Stage 2: test
# Extends base. Adds test tooling, runs tests, writes coverage to /out/.
# Mount a host directory to /out to retrieve reports:
#   docker run --rm -v $(pwd)/coverage:/out jobregator-test:latest
#
# TODO: Install your test runner and configure coverage output, e.g.:
#   RUN go install gotest.tools/gotestsum@v1.12.0
#   ENTRYPOINT ["gotestsum", "--jsonfile", "/out/tests.json", \
#               "--", "-coverprofile=/out/coverage.out", "./..."]
# =============================================================================
FROM base AS test

# TODO: Install test dependencies not present in base, e.g.:
#   RUN apk add --no-cache <test-dep>

# Placeholder entrypoint — replace with real test runner command
ENTRYPOINT ["sh", "-c", "echo 'TODO: replace with real test command' && exit 0"]

# =============================================================================
# Stage 3: artifact
# Minimal distributable image. Copies only the built binary/assets from base.
# Runs as a non-root user. This is what gets deployed / scanned.
# =============================================================================
FROM alpine:3.21.3 AS artifact

# Remove apk to reduce attack surface
RUN rm -f /sbin/apk && \
    rm -rf /etc/apk /lib/apk /usr/share/apk /var/lib/apk

# TODO: Copy built artifact(s) from base, e.g.:
#   COPY --from=base /app/myapp /home/nonroot/myapp
#   COPY --from=base /app/src/static /home/nonroot/static

# Expose application port
# TODO: Update to match your application's port
EXPOSE 8080

# Create non-root user and group
RUN addgroup --system nonroot && \
    adduser --system --ingroup nonroot nonroot

ENV HOME=/home/nonroot

RUN chown -R nonroot:nonroot $HOME && \
    chown -R nonroot:nonroot /tmp

USER nonroot
WORKDIR /home/nonroot

# TODO: Replace with real entrypoint, e.g.:
#   ENTRYPOINT ["./myapp"]
ENTRYPOINT ["sh", "-c", "echo 'TODO: replace with real entrypoint'"]

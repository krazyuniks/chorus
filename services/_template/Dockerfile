# Chorus service Dockerfile template.
#
# Convention: each service under `services/<name>/` copies this file
# verbatim and customises only the EXPOSE line, the OTEL_SERVICE_NAME
# default, and the runtime CMD. The multi-stage layout caches dependency
# installs separately from app code.
#
# Build args (set automatically by `scripts/dc`):
#   UID, GID         — host user mapping for bind-mounted volumes.
#   SERVICE_VERSION  — git SHA at build time, falls back to `dev`. Surfaces
#                      as `service.version` on every emitted span/log/metric
#                      per ADR 0010.
#
# Customise per-service:
#   - Adjust EXPOSE to the service's listening port.
#   - Set OTEL_SERVICE_NAME to the service name (e.g. `chorus-bff`).
#   - Replace CMD with the service's entrypoint, kept under
#     `opentelemetry-instrument` so auto-instrumentation stays on.

# -----------------------------------------------------------------------------
# Stage 1 — builder: install dependencies into a hermetic .venv, then layer
# in the OpenTelemetry per-library auto-instrumentations matching what the
# service actually depends on (ADR 0010 §2).
# -----------------------------------------------------------------------------
FROM python:3.14-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

COPY pyproject.toml ./
COPY uv.lock* ./

RUN uv sync --frozen --no-dev --no-install-project || uv sync --no-dev --no-install-project

# Per-library auto-instrumentation: walks the resolved venv, installs the
# matching opentelemetry-instrumentation-* packages for each library found.
# Idempotent. Run after `uv sync` so it sees the final dependency set.
RUN /app/.venv/bin/opentelemetry-bootstrap -a install

# -----------------------------------------------------------------------------
# Stage 2 — runtime: minimal image, non-root user matching host UID/GID,
# OpenTelemetry resource attributes baked into the env, and
# `opentelemetry-instrument` as the entrypoint so CMD stays simple.
# -----------------------------------------------------------------------------
FROM python:3.14-slim AS runtime

ARG UID=1000
ARG GID=1000
ARG SERVICE_VERSION=dev

RUN groupadd --gid "${GID}" appgroup \
    && useradd --uid "${UID}" --gid appgroup --create-home --shell /bin/bash appuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:${PATH}" \
    OTEL_SERVICE_NAME=chorus-service-template \
    OTEL_RESOURCE_ATTRIBUTES=service.namespace=chorus,deployment.environment=local,service.version=${SERVICE_VERSION} \
    OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317 \
    OTEL_EXPORTER_OTLP_PROTOCOL=grpc \
    OTEL_TRACES_EXPORTER=otlp \
    OTEL_METRICS_EXPORTER=otlp \
    OTEL_LOGS_EXPORTER=otlp \
    OTEL_PROPAGATORS=tracecontext,baggage

WORKDIR /app

COPY --from=builder --chown=appuser:appgroup /app/.venv /app/.venv
COPY --chown=appuser:appgroup . /app

USER appuser

# Override per service.
EXPOSE 8000

# `opentelemetry-instrument` is the auto-instrumentation runner. It sets up
# the SDK with the env-driven config above and execs the wrapped command.
# Override CMD per service, keeping the wrapper.
ENTRYPOINT ["opentelemetry-instrument"]

# Override per service. Default is a no-op so an unconfigured service fails
# loudly instead of silently starting the wrong process.
CMD ["python", "-c", "raise SystemExit('configure CMD in this service Dockerfile')"]

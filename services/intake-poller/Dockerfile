# Chorus intake/worker runtime.
#
# This service keeps the Temporal worker under the service-template
# OpenTelemetry entrypoint so workflow/activity spans, metrics, and logs flow
# through the local observability stack.

FROM python:3.14-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

COPY services/intake-poller/pyproject.toml ./pyproject.toml
COPY uv.lock* ./

RUN uv sync --frozen --no-dev --no-install-project || uv sync --no-dev --no-install-project
RUN /app/.venv/bin/opentelemetry-bootstrap -a install

FROM python:3.14-slim AS runtime

ARG UID=1000
ARG GID=1000
ARG SERVICE_VERSION=dev

RUN groupadd --gid "${GID}" appgroup \
    && useradd --uid "${UID}" --gid appgroup --create-home --shell /bin/bash appuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PATH="/app/.venv/bin:${PATH}" \
    OTEL_SERVICE_NAME=chorus-intake-poller \
    OTEL_RESOURCE_ATTRIBUTES=service.namespace=chorus,deployment.environment=local,service.version=${SERVICE_VERSION} \
    OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317 \
    OTEL_EXPORTER_OTLP_PROTOCOL=grpc \
    OTEL_TRACES_EXPORTER=otlp \
    OTEL_METRICS_EXPORTER=otlp \
    OTEL_LOGS_EXPORTER=otlp \
    OTEL_PROPAGATORS=tracecontext,baggage

WORKDIR /app

COPY --from=builder --chown=appuser:appgroup /app/.venv /app/.venv
COPY --chown=appuser:appgroup chorus /app/chorus

USER appuser

ENTRYPOINT ["opentelemetry-instrument"]
CMD ["python", "-m", "chorus.workflows.worker"]

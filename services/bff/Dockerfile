# Chorus BFF runtime.
#
# Serves the Lighthouse UI's read-only projection, audit, runtime-policy, and
# progress-stream endpoints under the standard OpenTelemetry entrypoint.

FROM python:3.14-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

COPY services/bff/pyproject.toml ./pyproject.toml
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
    OTEL_SERVICE_NAME=chorus-bff \
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

EXPOSE 8000

ENTRYPOINT ["opentelemetry-instrument"]
CMD ["uvicorn", "chorus.bff.app:app", "--host", "0.0.0.0", "--port", "8000"]

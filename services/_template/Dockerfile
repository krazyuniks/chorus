# Chorus service Dockerfile template.
#
# Convention: each service under `services/<name>/` copies this file
# verbatim and customises only the EXPOSE line and the runtime CMD. The
# multi-stage layout caches dependency installs separately from app code.
#
# Build args (set automatically by `scripts/dc`):
#   UID, GID — host user mapping for bind-mounted volumes.
#
# Customise per-service:
#   - Adjust EXPOSE to the service's listening port.
#   - Replace CMD with the service's entrypoint (e.g. uvicorn, a worker).

# -----------------------------------------------------------------------------
# Stage 1 — builder: install dependencies into a hermetic .venv.
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

# -----------------------------------------------------------------------------
# Stage 2 — runtime: minimal image, non-root user matching host UID/GID.
# -----------------------------------------------------------------------------
FROM python:3.14-slim AS runtime

ARG UID=1000
ARG GID=1000

RUN groupadd --gid "${GID}" appgroup \
    && useradd --uid "${UID}" --gid appgroup --create-home --shell /bin/bash appuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

COPY --from=builder --chown=appuser:appgroup /app/.venv /app/.venv
COPY --chown=appuser:appgroup . /app

USER appuser

# Override per service.
EXPOSE 8000

# Override per service. Default is a no-op so an unconfigured service fails
# loudly instead of silently starting the wrong process.
CMD ["python", "-c", "raise SystemExit('configure CMD in this service Dockerfile')"]

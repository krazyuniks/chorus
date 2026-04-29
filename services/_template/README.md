# Service template

Reference layout for a new Chorus Phase 1 service. Copy the entire directory,
rename it, and customise.

## Usage

```zsh
cp -r services/_template services/my-service
```

Then in the new directory:

1. Rename the project in `pyproject.toml` (`name = "chorus-my-service"`).
2. Add runtime dependencies under `[project] dependencies = [...]`. Keep
   `opentelemetry-distro[otlp]` — it is the auto-instrumentation bedrock per
   [ADR 0010](../../adrs/0010-observability-pipeline.md).
3. Edit `Dockerfile`:
   - Set `EXPOSE` to the service's listening port.
   - Set `OTEL_SERVICE_NAME` to the service name (e.g. `chorus-bff`).
   - Replace the placeholder `CMD` with the service entrypoint, **keeping
     it under the `opentelemetry-instrument` ENTRYPOINT** (for example
     `CMD ["uvicorn", "chorus_my_service.app:app", "--host", "0.0.0.0", "--port", "8000"]`).
4. Wire the service into `compose.yml` using `${UID:-1000}:${GID:-1000}` for the
   `user:` line and the `${MY_SERVICE_PORT:-...}` pattern for ports. Add a
   `depends_on: chown-init: { condition: service_completed_successfully }`
   entry if the service bind-mounts host paths. If the service emits
   telemetry, also depend on `otel-collector: { condition: service_started }`.
5. Document the new service in `docs/architecture.md` and add tests under
   `tests/services/<name>/`.

## Conventions enforced by the template

- Multi-stage build: dependencies install in the builder stage, runtime image
  copies only the resolved `.venv`.
- Non-root execution: `appuser:appgroup` matches host UID/GID via `ARG UID`
  and `ARG GID`.
- `PYTHONUNBUFFERED=1` so logs flush immediately under Docker.
- The default `CMD` deliberately fails — every service must declare its own.
- OpenTelemetry auto-instrumentation is on by default. The builder stage
  runs `opentelemetry-bootstrap -a install` after dependency resolution so
  every library the service actually depends on (FastAPI, httpx, asyncpg,
  psycopg, …) is auto-instrumented. The runtime image's `ENTRYPOINT` is
  `opentelemetry-instrument`, and `OTEL_*` env vars set the resource
  attributes (`service.name`, `service.namespace=chorus`,
  `deployment.environment=local`, `service.version`) and OTLP exporter
  target (`http://otel-collector:4317`) per ADR 0010.

## Capturing trace IDs in audit rows

Audit-write code that needs to record the active OTel trace/span IDs into
the row's `metadata` jsonb (per ADR 0010 §4) imports the helper from the
shared `chorus.observability` package:

```python
from chorus.observability import current_otel_ids

metadata = {**existing_metadata, **current_otel_ids()}
```

The helper returns an empty dict when no SDK is installed or no span is
active, so it is safe to call from persistence and test code.

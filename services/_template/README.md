# Service template

Reference layout for a new Chorus Phase 1 service. Copy the entire directory,
rename it, and customise.

## Usage

```zsh
cp -r services/_template services/my-service
```

Then in the new directory:

1. Rename the project in `pyproject.toml` (`name = "chorus-my-service"`).
2. Add runtime dependencies under `[project] dependencies = [...]`.
3. Edit `Dockerfile`:
   - Set `EXPOSE` to the service's listening port.
   - Replace the placeholder `CMD` with the service entrypoint (for example
     `["uvicorn", "chorus_my_service.app:app", "--host", "0.0.0.0", "--port", "8000"]`).
4. Wire the service into `compose.yml` using `${UID:-1000}:${GID:-1000}` for the
   `user:` line and the `${MY_SERVICE_PORT:-...}` pattern for ports. Add a
   `depends_on: chown-init: { condition: service_completed_successfully }`
   entry if the service bind-mounts host paths.
5. Document the new service in `docs/architecture.md` and add tests under
   `tests/services/<name>/`.

## Conventions enforced by the template

- Multi-stage build: dependencies install in the builder stage, runtime image
  copies only the resolved `.venv`.
- Non-root execution: `appuser:appgroup` matches host UID/GID via `ARG UID`
  and `ARG GID`.
- `PYTHONUNBUFFERED=1` so logs flush immediately under Docker.
- The default `CMD` deliberately fails — every service must declare its own.

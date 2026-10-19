# Orbit backend

A Python 3.13+ HTTP API built with FastAPI, Pydantic validation, and Uvicorn.

## Get started

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run:

```sh
uv sync --locked
make dev
```

uv manages the Python environment and dependencies; no manual activation is needed.
The development server listens at http://127.0.0.1:8000 and reloads on changes.
Interactive documentation is available at `/docs`, with OpenAPI JSON at `/openapi.json`.

```sh
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/api/v1/echo \
  -H 'Content-Type: application/json' \
  -d '{"message":"Hello, Orbit!"}'
```

`GET /health` returns `{"status":"ok"}`. `POST /api/v1/echo` accepts a JSON
`message` of 1–1,000 characters after trimming whitespace and returns it. Invalid
requests receive HTTP 422. The echo endpoint is an example and stores no data.

## Development tools

- **uv** manages dependencies, the virtual environment, packaging, and `uv.lock`.
- **Ruff** checks imports and code quality and formats Python files.
- **mypy** checks application and test types in strict mode.
- **pytest + HTTPX** test the API; **pytest-cov** enforces 100% branch/line coverage.
- **pre-commit** runs Ruff and mypy before commits when installed.
- **GitHub Actions** runs quality checks, tests, and a package build on pushes and PRs.

```sh
make format       # Fix lint issues and format
make check        # Lint, formatting check, type check, tests with coverage
uv build          # Build wheel and source distribution
```

After initializing or cloning a Git repository, run `make hooks` to install
pre-commit hooks. Run `uv run pre-commit run --all-files` to check tracked files.
Commit `uv.lock`; update dependencies intentionally using `uv lock --upgrade`,
then `uv sync --locked` and `make check`.

## Layout

Application code lives in `src/orbit_backend/`; API tests live in `tests/`.
`create_app()` creates an independent application for each test or server process.
Add feature-specific routers and models as the API grows.

## Serving

`make serve` binds to `0.0.0.0:8000` without development reload. For an installed
production environment use `uv sync --locked --no-dev`, then
`uv run --no-dev uvicorn orbit_backend.main:create_app --factory --host 0.0.0.0 --port 8000`.
Configure HTTPS and access controls at deployment before adding private data or
exposing protected operations. No database, authentication, or external API key
is required for this starter. Keep credentials out of version control.

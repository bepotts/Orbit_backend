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
Docker and the Supabase CLI must be installed and running. `make dev` starts the
local stack and refreshes the ignored `.env.development` file automatically.
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
- **pytest + HTTPX2** test the API; **pytest-cov** enforces 100% branch/line coverage.
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

`make serve` selects production and binds to `0.0.0.0:8000` without development reload. For an installed
production environment use `uv sync --locked --no-dev`, then
`APP_ENV=production uv run --no-dev uvicorn orbit_backend.main:create_app --factory --host 0.0.0.0 --port 8000`.
Configure HTTPS and access controls at deployment before adding private data or
exposing protected operations. The health and echo endpoints run without Supabase credentials. Keep credentials out of version control.

## Docker

Use `Dockerfile` for production and `Dockerfile.dev` for development. Run these
commands from the backend directory.

### Production

```sh
make docker-prod
```

Populate `.env` with your hosted `SUPABASE_URL` and `SUPABASE_KEY` first (see
`.env.example`). The command builds the production image and runs it in the
foreground with `APP_ENV=production`. Credentials are supplied at runtime
and excluded from the build context. The container runs as a non-root user,
installs only locked production dependencies, and checks `/health` automatically.
The API is available at http://localhost:8000 and its documentation at `/docs`.
This image runs the API; local Supabase is managed separately with the existing
development commands.

### Development

```sh
make docker-dev
```

The command starts local Supabase, refreshes `.env.development`, builds the
development image, and runs the API in the foreground. Stop either API container
with Ctrl+C; local Supabase keeps running until `make supabase-stop`.

Host networking lets the API reach local Supabase at `127.0.0.1:54321` without
changing the development URL checks. On Docker Desktop, enable host networking
in Settings → Resources → Network first. Port publishing (`-p`) is unnecessary
with host networking. The API listens at http://localhost:8000.

The project mount supplies `.env.development` and reloads the API when files in
`src` change. Development dependencies (including pytest, Ruff, and mypy) are
installed in `/opt/venv`, separate from your host's `.venv`. After changing
`pyproject.toml` or `uv.lock`, rebuild the image and restart the container.
Run the tests inside the running development container with:

```sh
docker exec orbit-backend-dev uv run --locked pytest
```

The Supabase CLI runs on the host using the existing Make targets.

## Supabase

The official async Python SDK is installed and pinned in `pyproject.toml` and
`uv.lock`. Development (the default `APP_ENV=development`) reads only
`.env.development`, generated from your running local Supabase stack. Production
(`APP_ENV=production`) reads only `.env` or deployment environment variables.
For production, copy `.env.example` to `.env` and set `SUPABASE_URL` and
`SUPABASE_KEY` from your hosted project's Connect dialog. Environment variables
override the selected dotenv file. Both dotenv files are Git-ignored.

Use a publishable key for operations governed by Row Level Security (RLS).
Secret/service-role keys bypass RLS: keep them server-only and use them only in
explicitly authorized admin operations. No privileged key is needed for this setup.


## Local development versus production

```sh
make dev              # Start local Supabase, refresh .env.development, run with reload
make supabase-env     # Refresh only the local credentials file
make supabase-stop    # Stop local containers, preserving database volumes
make serve            # Run against hosted Supabase using .env or deployment variables
```

Local Supabase API: `http://127.0.0.1:54321`; Studio: `http://127.0.0.1:54323`;
email inbox: `http://127.0.0.1:54324`. Local users and data are separate from the
hosted project. The existing `supabase/config.toml` controls your local stack.
The credential setup script uses the local publishable key (or anon compatibility
key) and never copies the service-role key. It preserves your production `.env`.

Startup rejects cloud URLs in development. Production requires an HTTPS
`*.supabase.co` URL and a nonempty key, and never falls back to local Supabase.
Missing production configuration fails startup. For deployment, set
`APP_ENV=production`, `SUPABASE_URL`, and `SUPABASE_KEY` in the host's environment.
If your shell already exports hosted Supabase variables, unset those while running
`make dev` so they do not override `.env.development`.

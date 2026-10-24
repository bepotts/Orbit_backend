.PHONY: test-db setup dev serve docker-dev docker-prod format lint typecheck test check hooks supabase-start supabase-env supabase-stop
setup:
	uv sync --locked

dev: supabase-start supabase-env
	APP_ENV=development uv run uvicorn orbit_backend.main:create_app --factory --reload

serve:
	APP_ENV=production uv run uvicorn orbit_backend.main:create_app --factory --host 0.0.0.0 --port 8000

# Start local services before refreshing credentials, then run with source reload.
docker-dev: supabase-start
	$(MAKE) supabase-env
	docker build -f Dockerfile.dev -t orbit-backend:dev .
	docker run --rm --name orbit-backend-dev --network host \
		--mount "type=bind,source=$(CURDIR),target=/app" \
		-e APP_ENV=development orbit-backend:dev

# Supply hosted credentials at runtime and explicitly select production mode.
docker-prod:
	docker build -f Dockerfile -t orbit-backend:prod .
	docker run --rm --name orbit-backend -p 8000:8000 --env-file .env \
		-e APP_ENV=production orbit-backend:prod

format:
	uv run ruff check --fix .
	uv run ruff format .

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run mypy

test:
	uv run pytest

check: lint typecheck test

hooks:
	uv run pre-commit install

# Local containers only; stopping preserves local database volumes.
supabase-start:
	supabase start

supabase-env:
	uv run python scripts/configure_local_supabase.py

supabase-stop:
	supabase stop

# SQL constraints and ownership policies; requires the running local Supabase stack.
test-db:
	supabase test db --local

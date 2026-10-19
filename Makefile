.PHONY: setup dev serve format lint typecheck test check hooks
setup:
	uv sync --locked

dev:
	uv run uvicorn orbit_backend.main:create_app --factory --reload

serve:
	uv run uvicorn orbit_backend.main:create_app --factory --host 0.0.0.0 --port 8000

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

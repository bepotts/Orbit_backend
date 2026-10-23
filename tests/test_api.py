"""Exercise HTTP behavior through the ASGI application."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from orbit_backend.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Provide an isolated client with application lifespan management."""
    with TestClient(create_app()) as test_client:
        yield test_client


def test_health(client: TestClient) -> None:
    """The health endpoint reports liveness as JSON."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unknown_route(client: TestClient) -> None:
    """Unknown paths produce a standard not-found response."""
    assert client.get("/missing").status_code == 404


def test_openapi(client: TestClient) -> None:
    """API documentation describes the current health and user endpoints."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert {"/health", "/api/v1/users", "/api/v1/users/login"} <= response.json()["paths"].keys()

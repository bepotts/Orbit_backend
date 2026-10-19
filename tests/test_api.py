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


def test_echo(client: TestClient) -> None:
    """Valid input is trimmed and returned."""
    response = client.post("/api/v1/echo", json={"message": " Hello, Orbit! "})
    assert response.status_code == 200
    assert response.json() == {"message": "Hello, Orbit!"}


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"message": ""},
        {"message": "   "},
        {"message": "x" * 1001},
        {"message": 42},
        {"message": "hello", "unexpected": True},
    ],
)
def test_echo_rejects_invalid_input(client: TestClient, payload: dict[str, object]) -> None:
    """Missing, invalid, or extra fields produce validation errors."""
    assert client.post("/api/v1/echo", json=payload).status_code == 422


def test_malformed_json(client: TestClient) -> None:
    """Malformed JSON produces a validation error."""
    response = client.post(
        "/api/v1/echo", content="{", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422


def test_unknown_route(client: TestClient) -> None:
    """Unknown paths produce a standard not-found response."""
    assert client.get("/missing").status_code == 404


def test_openapi(client: TestClient) -> None:
    """API documentation describes both initial endpoints."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert {"/health", "/api/v1/echo"} <= response.json()["paths"].keys()

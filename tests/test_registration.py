"""Registration tests using the real Supabase SDK with a mocked HTTP service."""

import json
from collections.abc import Iterator
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import HttpUrl, SecretStr

from orbit_backend.config import Settings, get_settings
from orbit_backend.main import create_app

PAYLOAD = {
    "first_name": "Ada",
    "last_name": "Lovelace",
    "email": "ada@example.com",
    "password": "private-password",
}


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Provide an app with isolated fake credentials."""
    app = create_app()
    settings = Settings.model_construct(
        supabase_url=HttpUrl("https://example.supabase.co"), supabase_key=SecretStr("test-key")
    )
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.parametrize(
    ("upstream_status", "body", "expected"),
    [
        (
            200,
            {
                "id": "test-id",
                "app_metadata": {},
                "user_metadata": {},
                "aud": "authenticated",
                "created_at": "2026-10-20T00:00:00Z",
            },
            202,
        ),
        (200, {}, 502),
        (400, {"msg": "private-password", "code": "validation_failed"}, 400),
        (
            422,
            {
                "msg": "private-password",
                "code": "weak_password",
                "weak_password": {"reasons": ["length"]},
            },
            400,
        ),
        (422, {"msg": "already registered", "code": "user_already_exists"}, 202),
        (429, {"msg": "rate limited"}, 429),
        (500, {"msg": "server failure"}, 503),
    ],
)
def test_registration(
    client: TestClient, upstream_status: int, body: dict[str, object], expected: int
) -> None:
    """Verify signup credentials, metadata, and sanitized response handling."""

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/auth/v1/signup"
        data = json.loads(request.content)
        assert data["email"] == PAYLOAD["email"]
        assert data["password"] == PAYLOAD["password"]
        assert data["data"] == {"first_name": "Ada", "last_name": "Lovelace"}
        return httpx.Response(
            upstream_status, json=body, headers={"x-supabase-api-version": "2024-01-01"}
        )

    transport = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    with patch("orbit_backend.database.supabase.HTTPClient", return_value=transport):
        response = client.post("/api/v1/users", json=PAYLOAD)
    assert response.status_code == expected
    assert "private-password" not in response.text
    assert transport.is_closed


def test_network_failure(client: TestClient) -> None:
    """Network failures produce a sanitized service-unavailable response."""

    def respond(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("private-password", request=request)

    transport = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    with patch("orbit_backend.database.supabase.HTTPClient", return_value=transport):
        response = client.post("/api/v1/users", json=PAYLOAD)
    assert response.status_code == 503
    assert "private-password" not in response.text


def test_invalid_registration(client: TestClient) -> None:
    """Invalid input produces 422 without reflecting sensitive submitted values."""
    transport = httpx.AsyncClient()
    with patch("orbit_backend.database.supabase.HTTPClient", return_value=transport):
        response = client.post(
            "/api/v1/users", json={**PAYLOAD, "password": {"secret": "private-password"}}
        )
    assert response.status_code == 422
    assert "private-password" not in response.text

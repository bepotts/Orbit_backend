"""Exercise login through the real Supabase SDK without network access."""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import HttpUrl, SecretStr
from supabase import AsyncClient
from supabase_auth.types import AuthResponse

from orbit_backend.config import Settings, get_settings
from orbit_backend.database.supabase import get_supabase
from orbit_backend.main import create_app

PAYLOAD = {"email": "ada@example.com", "password": " secret-password "}
SESSION = {
    "access_token": "access-token",
    "refresh_token": "refresh-token",
    "token_type": "bearer",
    "expires_in": 3600,
    "expires_at": 2000000000,
    "user": {
        "id": "user-id",
        "aud": "authenticated",
        "app_metadata": {},
        "user_metadata": {},
        "created_at": "2026-10-20T00:00:00Z",
    },
}


@pytest.mark.parametrize(
    ("upstream_status", "body", "expected"),
    [
        (200, SESSION, 200),
        (200, {}, 502),
        (400, {"msg": "secret-password", "code": "invalid_credentials"}, 401),
        (400, {"msg": "email not confirmed", "code": "email_not_confirmed"}, 401),
        (429, {"msg": "rate limited"}, 429),
        (500, {"msg": "service failed"}, 503),
    ],
)
def test_login(upstream_status: int, body: dict[str, object], expected: int) -> None:
    """Verify SDK credentials, safe errors, and the returned uncached session."""

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/auth/v1/token"
        assert request.url.params["grant_type"] == "password"
        sent = json.loads(request.content)
        assert sent["email"] == PAYLOAD["email"]
        assert sent["password"] == PAYLOAD["password"]
        return httpx.Response(upstream_status, json=body)

    app = create_app()
    settings = Settings.model_construct(
        supabase_url=HttpUrl("https://example.supabase.co"), supabase_key=SecretStr("test-key")
    )
    app.dependency_overrides[get_settings] = lambda: settings
    transport = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    with (
        patch("orbit_backend.database.supabase.HTTPClient", return_value=transport),
        TestClient(app) as client,
    ):
        response = client.post("/api/v1/users/login", json=PAYLOAD)
    assert response.status_code == expected
    assert "secret-password" not in response.text
    assert transport.is_closed
    if expected == 200:
        assert response.headers["Cache-Control"] == "no-store"
        assert response.json() == {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "token_type": "bearer",
            "expires_in": 3600,
            "expires_at": 2000000000,
            "user_id": "user-id",
        }


@pytest.mark.parametrize("failure", [True, False])
def test_missing_session_or_network_failure(failure: bool) -> None:
    """Missing sessions and transport failures are mapped to safe HTTP errors."""
    supabase = AsyncMock(spec=AsyncClient)
    supabase.auth = AsyncMock()
    if failure:
        supabase.auth.sign_in_with_password.side_effect = httpx.ConnectError("secret-password")
    else:
        supabase.auth.sign_in_with_password.return_value = AuthResponse()
    app = create_app()
    app.dependency_overrides[get_supabase] = lambda: supabase
    with TestClient(app) as client:
        response = client.post("/api/v1/users/login", json=PAYLOAD)
    assert response.status_code == (503 if failure else 502)
    assert "secret-password" not in response.text


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"email": "invalid", "password": "secret-password"},
        {"email": "ada@example.com", "password": ""},
    ],
)
def test_invalid_login(payload: dict[str, str]) -> None:
    """Invalid login bodies fail before the SDK sign-in method is called."""
    supabase = AsyncMock(spec=AsyncClient)
    supabase.auth = AsyncMock()
    app = create_app()
    app.dependency_overrides[get_supabase] = lambda: supabase
    with TestClient(app) as client:
        response = client.post("/api/v1/users/login", json=payload)
    assert response.status_code == 422
    assert "secret-password" not in response.text
    supabase.auth.sign_in_with_password.assert_not_called()

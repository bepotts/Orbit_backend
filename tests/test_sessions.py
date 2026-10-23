"""Session lifecycle tests against the real SDK and mocked Supabase HTTP responses."""

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

USER: dict[str, object] = {
    "id": "user-id",
    "email": "ada@example.com",
    "aud": "authenticated",
    "app_metadata": {},
    "user_metadata": {},
    "created_at": "2026-10-21T00:00:00Z",
}
SESSION: dict[str, object] = {
    "access_token": "new-access-token",
    "refresh_token": "new-refresh-token",
    "token_type": "bearer",
    "expires_in": 3600,
    "expires_at": 2000000000,
    "user": USER,
}


@pytest.mark.parametrize("operation", ["signin", "refresh", "current", "signout"])
@pytest.mark.parametrize("upstream_status", [200, 400, 429, 500, 502])
def test_session_operations(operation: str, upstream_status: int) -> None:
    """Exercise successful operations, invalid credentials, throttling, and outages."""

    def respond(request: httpx.Request) -> httpx.Response:
        if operation in {"signin", "refresh"}:
            assert request.url.path == "/auth/v1/token"
            body = json.loads(request.content)
            if operation == "refresh":
                assert request.url.params["grant_type"] == "refresh_token"
                assert body["refresh_token"] == "old-refresh-token"
            else:
                assert body["password"] == "test-password"
            payload = SESSION
        else:
            assert request.headers["authorization"] == "Bearer user-access-token"
            payload = USER
            if operation == "signout":
                assert request.url.path == "/auth/v1/logout"
                assert request.url.params["scope"] == "local"
                if upstream_status == 200:
                    return httpx.Response(204)
            else:
                assert request.url.path == "/auth/v1/user"
        if upstream_status != 200:
            payload = {"msg": "private credential detail"}
        return httpx.Response(upstream_status, json=payload)

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
        if operation == "signin":
            response = client.post(
                "/api/v1/sessions", json={"email": "ada@example.com", "password": "test-password"}
            )
        elif operation == "refresh":
            response = client.post(
                "/api/v1/sessions/refresh", json={"refresh_token": "old-refresh-token"}
            )
        elif operation == "current":
            response = client.get(
                "/api/v1/sessions/current", headers={"Authorization": "Bearer user-access-token"}
            )
        else:
            response = client.delete(
                "/api/v1/sessions/current", headers={"Authorization": "Bearer user-access-token"}
            )
    assert transport.is_closed
    if upstream_status == 200:
        assert response.status_code == (204 if operation == "signout" else 200)
        assert response.headers["cache-control"] == "no-store"
        if operation in {"signin", "refresh"}:
            assert response.json()["access_token"] == "new-access-token"
            assert response.json()["refresh_token"] == "new-refresh-token"
        elif operation == "current":
            assert response.json() == {"id": "user-id", "email": "ada@example.com"}
        else:
            assert response.content == b""
    else:
        assert response.status_code == {400: 401, 429: 429, 500: 503, 502: 503}[upstream_status]
        assert "private credential detail" not in response.text


@pytest.mark.parametrize("method", ["get", "delete"])
@pytest.mark.parametrize("authorization", [None, "Basic wrong", "Bearer"])
def test_token_required(method: str, authorization: str | None) -> None:
    """Protected operations reject absent or malformed bearer credentials."""
    app = create_app()
    app.dependency_overrides[get_supabase] = lambda: AsyncMock(spec=AsyncClient)
    headers = {} if authorization is None else {"Authorization": authorization}
    with TestClient(app) as client:
        response = client.request(method, "/api/v1/sessions/current", headers=headers)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize("operation", ["refresh", "current"])
@pytest.mark.parametrize("mode", ["invalid", "empty", "network"])
def test_bad_session_responses(operation: str, mode: str) -> None:
    """Invalid upstream payloads, absent sessions, and network failures are handled."""
    app = create_app()
    supabase = AsyncMock(spec=AsyncClient)
    supabase.auth = AsyncMock()
    result = None if operation == "current" else AuthResponse()
    target = supabase.auth.get_user if operation == "current" else supabase.auth.refresh_session
    if mode == "network":
        target.side_effect = httpx.ConnectError("secret-token")
    elif mode == "invalid":
        from pydantic import ValidationError

        from orbit_backend.models import LoginRequest

        try:
            LoginRequest.model_validate({})
        except ValidationError as error:
            target.side_effect = error
    else:
        target.return_value = result
    app.dependency_overrides[get_supabase] = lambda: supabase
    with TestClient(app) as client:
        response = (
            client.get("/api/v1/sessions/current", headers={"Authorization": "Bearer access"})
            if operation == "current"
            else client.post("/api/v1/sessions/refresh", json={"refresh_token": "refresh"})
        )
    expected = 503 if mode == "network" else 502
    if mode == "empty" and operation == "current":
        expected = 401
    assert response.status_code == expected
    assert "secret-token" not in response.text


def test_refresh_validation() -> None:
    """Refresh requires a nonempty token and hides invalid input values."""
    app = create_app()
    app.dependency_overrides[get_supabase] = lambda: AsyncMock(spec=AsyncClient)
    with TestClient(app) as client:
        assert (
            client.post("/api/v1/sessions/refresh", json={"refresh_token": ""}).status_code == 422
        )

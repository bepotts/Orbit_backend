"""Verify settings and SDK integration without cloud credentials."""

import asyncio
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from orbit_backend.config import Settings, get_settings
from orbit_backend.database.supabase import SupabaseDependency
from orbit_backend.main import create_app


@pytest.fixture(autouse=True)
def isolate_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep configuration tests independent of local credentials and dotenv files."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)


def test_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Environment overrides dotenv values, and credentials are redacted."""
    monkeypatch.chdir(tmp_path)
    Path(".env").write_text("SUPABASE_URL=https://dotenv.supabase.co\nSUPABASE_KEY=dotenv-key\n")
    monkeypatch.setenv("SUPABASE_URL", "https://environment.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "environment-key")
    settings = get_settings()
    assert str(settings.supabase_url) == "https://environment.supabase.co/"
    assert settings.supabase_key is not None
    assert settings.supabase_key.get_secret_value() == "environment-key"
    assert "environment-key" not in repr(settings)


def test_invalid_url() -> None:
    """Invalid URL configuration is rejected."""
    with pytest.raises(ValidationError):
        Settings(supabase_url="not-a-url")


@pytest.mark.parametrize(
    "values", [{}, {"supabase_url": "https://example.supabase.co"}, {"supabase_key": "key"}]
)
def test_missing_configuration(values: dict[str, str]) -> None:
    """Incomplete settings produce 503 without affecting liveness."""
    app = create_app()
    settings = Settings.model_validate(values)
    app.dependency_overrides[get_settings] = lambda: settings

    @app.get("/supabase-test")
    async def endpoint(supabase: SupabaseDependency) -> None:
        pass

    with TestClient(app) as client:
        assert client.get("/supabase-test").status_code == 503
        assert client.get("/health").status_code == 200


@pytest.mark.parametrize("fail", [False, True])
def test_sdk_query_and_cleanup(fail: bool) -> None:
    """A real SDK query sends API credentials and closes transport on failure too."""

    async def run() -> None:
        def respond(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/rest/v1/example"
            assert request.url.params["select"] == "id"
            assert request.headers["apikey"] == "test-key"
            return httpx.Response(200, json=[{"id": 1}])

        transport = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        app = create_app()
        settings = Settings.model_validate(
            {"supabase_url": "https://example.supabase.co", "supabase_key": "test-key"}
        )
        app.dependency_overrides[get_settings] = lambda: settings

        @app.get("/supabase-test")
        async def endpoint(supabase: SupabaseDependency) -> object:
            assert not supabase.options.persist_session
            assert not supabase.options.auto_refresh_token
            response = await supabase.table("example").select("id").execute()
            if fail:
                raise RuntimeError("test failure")
            return response.data

        with patch("orbit_backend.database.supabase.HTTPClient", return_value=transport):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                base_url="http://test",
            ) as client:
                response = await client.get("/supabase-test")
        assert transport.is_closed
        if fail:
            assert response.status_code == 500
        else:
            assert response.status_code == 200
            assert response.json() == [{"id": 1}]

    asyncio.run(run())

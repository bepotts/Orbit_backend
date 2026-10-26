"""Ensure development and production cannot accidentally share Supabase targets."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from orbit_backend.config import get_settings
from orbit_backend.main import create_app
from orbit_backend.utils.enums import Environment


@pytest.fixture(autouse=True)
def isolate_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Remove machine-specific credentials and use an isolated working directory."""
    monkeypatch.chdir(tmp_path)
    for name in ("APP_ENV", "SUPABASE_URL", "SUPABASE_KEY"):
        monkeypatch.delenv(name, raising=False)


def test_development_ignores_production_file() -> None:
    """Default development settings never load the production dotenv file."""
    Path(".env").write_text("SUPABASE_URL=https://hosted.supabase.co\nSUPABASE_KEY=hosted-key\n")
    settings = get_settings()
    assert str(settings.supabase_url) == "http://127.0.0.1:54321/"
    assert settings.app_env is Environment.DEVELOPMENT
    assert settings.supabase_key is None


def test_production_ignores_development_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """Production selects hosted credentials even when local credentials exist."""
    monkeypatch.setenv("APP_ENV", Environment.PRODUCTION)
    Path(".env.development").write_text(
        "SUPABASE_URL=http://localhost:54321\nSUPABASE_KEY=local-key\n"
    )
    Path(".env").write_text("SUPABASE_URL=https://hosted.supabase.co\nSUPABASE_KEY=hosted-key\n")
    settings = get_settings()
    assert str(settings.supabase_url) == "https://hosted.supabase.co/"
    assert settings.app_env is Environment.PRODUCTION
    assert settings.supabase_key is not None
    assert settings.supabase_key.get_secret_value() == "hosted-key"
    with TestClient(create_app()) as client:
        assert client.get("/health").status_code == 200


@pytest.mark.parametrize(
    "url",
    [
        None,
        "http://127.0.0.1:54321",
        "https://localhost:54321",
        "http://hosted.supabase.co",
        "https://example.com",
    ],
)
def test_invalid_production_fails_at_startup(
    url: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Missing credentials and non-hosted URLs prevent production startup."""
    monkeypatch.setenv("APP_ENV", Environment.PRODUCTION)
    monkeypatch.setenv("SUPABASE_KEY", "test-key")
    if url is not None:
        monkeypatch.setenv("SUPABASE_URL", url)
    with pytest.raises(ValueError), TestClient(create_app()):
        pass


def test_production_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """A hosted URL alone is insufficient for production."""
    monkeypatch.setenv("APP_ENV", Environment.PRODUCTION)
    monkeypatch.setenv("SUPABASE_URL", "https://hosted.supabase.co")
    with pytest.raises(ValueError):
        get_settings()


def test_development_rejects_cloud(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exported hosted variables cannot silently override local development."""
    monkeypatch.setenv("SUPABASE_URL", "https://hosted.supabase.co")
    with pytest.raises(ValueError):
        get_settings()


def test_invalid_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Misspelled environment names fail validation rather than selecting a target."""
    monkeypatch.setenv("APP_ENV", "prodution")
    with pytest.raises(ValueError):
        get_settings()

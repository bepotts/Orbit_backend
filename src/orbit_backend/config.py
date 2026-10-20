"""Environment-based service configuration."""

import os
from typing import Literal

from pydantic import HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Load Supabase configuration for the selected application environment."""

    model_config = SettingsConfigDict(extra="ignore", env_ignore_empty=True)

    app_env: Literal["development", "production"] = "development"
    supabase_url: HttpUrl | None = None
    supabase_key: SecretStr | None = None


def get_settings() -> Settings:
    """Select isolated dotenv files and prevent cross-environment Supabase connections."""
    environment = os.environ.get("APP_ENV", "development")
    settings = Settings(
        _env_file=".env" if environment == "production" else ".env.development",
        app_env=environment,
    )
    if settings.app_env == "production":
        if settings.supabase_url is None or settings.supabase_key is None:
            raise ValueError("Production requires SUPABASE_URL and SUPABASE_KEY")
        if settings.supabase_url.scheme != "https" or not (
            settings.supabase_url.host or ""
        ).endswith(".supabase.co"):
            raise ValueError("Production requires an HTTPS hosted Supabase project URL")
    else:
        if settings.supabase_url is None:
            settings.supabase_url = HttpUrl("http://127.0.0.1:54321")
        if settings.supabase_url.host not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("Development requires local Supabase; run make supabase-env")
    return settings

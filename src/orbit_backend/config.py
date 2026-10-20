"""Environment-based service configuration."""

from pydantic import HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Load optional Supabase credentials from the environment or local .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

    supabase_url: HttpUrl | None = None
    supabase_key: SecretStr | None = None


def get_settings() -> Settings:
    """Load settings; environment variables take precedence over .env values."""
    return Settings()

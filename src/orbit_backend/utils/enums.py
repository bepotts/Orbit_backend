"""Supported application deployment environments."""

from enum import StrEnum


class Environment(StrEnum):
    """Represent the supported values of APP_ENV."""

    DEVELOPMENT = "development"
    PRODUCTION = "production"

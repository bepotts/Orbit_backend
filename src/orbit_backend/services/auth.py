"""Shared authentication error handling for session operations."""

from collections.abc import Generator
from contextlib import contextmanager

from fastapi import HTTPException
from httpx import RequestError
from pydantic import ValidationError
from supabase_auth.errors import AuthApiError, AuthError


@contextmanager
def auth_errors() -> Generator[None]:
    """Map Supabase errors to sanitized HTTP responses without exposing tokens."""
    try:
        yield
    except AuthApiError as error:
        if error.status == 429:
            raise HTTPException(429, "Too many authentication attempts") from None
        if error.status >= 500:
            raise HTTPException(503, "Authentication is temporarily unavailable") from None
        raise HTTPException(
            401, "Invalid or expired session", headers={"WWW-Authenticate": "Bearer"}
        ) from None
    except ValidationError:
        raise HTTPException(502, "Authentication returned an invalid response") from None
    except (AuthError, RequestError):
        raise HTTPException(503, "Authentication is temporarily unavailable") from None

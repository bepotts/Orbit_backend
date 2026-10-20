"""Validated application request and response models."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, StringConstraints


class HealthResponse(BaseModel):
    """Service liveness response."""

    status: Literal["ok"] = "ok"


class Message(BaseModel):
    """Validated JSON message accepted and returned by the example endpoint."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    message: str = Field(min_length=1, max_length=1000)


class User(BaseModel):
    """Validate user details and keep the password out of serialized output.

    This input model does not persist credentials or hash passwords.
    """

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    first_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    last_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    email: EmailStr
    password: SecretStr = Field(min_length=1, exclude=True)


class RegistrationResponse(BaseModel):
    """Acknowledge registration without disclosing account existence or credentials."""

    message: str = "Registration submitted. If email confirmation is required, check your inbox."


class LoginRequest(BaseModel):
    """Validate email/password login input without altering password whitespace."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    email: EmailStr
    password: SecretStr = Field(min_length=1, exclude=True)


class LoginResponse(BaseModel):
    """Return the session credentials required by the client to authenticate requests."""

    access_token: str = Field(repr=False)
    refresh_token: str = Field(repr=False)
    token_type: str
    expires_in: int
    expires_at: int | None
    user_id: str

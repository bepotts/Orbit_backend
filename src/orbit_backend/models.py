"""Validated application request and response models."""

from datetime import UTC, datetime
from typing import Annotated, Literal, Self
from uuid import UUID, uuid4

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    StringConstraints,
    model_validator,
)


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


class UserProfile(BaseModel):
    """Represent an existing user without including sign-up credentials."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    first_name: str
    last_name: str
    email: EmailStr


class TimerSession(BaseModel):
    """Capture the iOS timer state in seconds and associate it with a user profile.

    user_id references UserProfile.id. A running timer's end_date is authoritative;
    remaining_seconds is the value captured at captured_at, not a ticking counter.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    session_label: str = ""
    phase: Literal["idle", "running", "paused", "complete"] = "idle"
    duration_seconds: float = Field(default=1800, ge=0, le=6039, allow_inf_nan=False)
    total_duration_seconds: float = Field(default=1800, ge=0, le=6039, allow_inf_nan=False)
    remaining_seconds: float = Field(default=1800, ge=0, le=6039, allow_inf_nan=False)
    end_date: AwareDatetime | None = None
    captured_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_timer_state(self) -> Self:
        """Reject impossible countdown values and incomplete running snapshots."""
        if self.remaining_seconds > self.total_duration_seconds:
            raise ValueError("Remaining seconds cannot exceed the active total duration")
        if self.phase == "running" and self.end_date is None:
            raise ValueError("Running timers require an end date")
        if self.phase == "complete" and self.remaining_seconds != 0:
            raise ValueError("Completed timers must have zero remaining seconds")
        return self


class RefreshSessionRequest(BaseModel):
    """Carry a refresh token for session renewal without exposing it in representations."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    refresh_token: SecretStr = Field(min_length=1, exclude=True)


class SessionUser(BaseModel):
    """Return the verified session's account identity without credentials or metadata."""

    id: str
    email: str | None

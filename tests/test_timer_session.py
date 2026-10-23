"""Verify timer snapshots mirror iOS timing semantics and user ownership."""

from uuid import UUID

import pytest
from pydantic import ValidationError

from orbit_backend.models import TimerSession, UserProfile

USER_ID = "3d790554-214d-4d54-ace7-7e510d8726eb"


def test_user_association_and_defaults() -> None:
    """Sessions reference a password-free profile and default to the iOS 30 minutes."""
    profile = UserProfile.model_validate(
        {"id": USER_ID, "first_name": "Ada", "last_name": "Lovelace", "email": "ada@example.com"}
    )
    session = TimerSession(user_id=profile.id)
    assert session.user_id == profile.id
    assert (
        session.duration_seconds
        == session.total_duration_seconds
        == session.remaining_seconds
        == 1800
    )
    assert session.phase == "idle"
    assert session.end_date is None
    assert session.captured_at.utcoffset() is not None
    assert "password" not in profile.model_dump()
    assert TimerSession(user_id=profile.id).id != session.id


@pytest.mark.parametrize("phase", ["idle", "running", "paused", "complete"])
def test_snapshot_round_trip(phase: str) -> None:
    """Fractional seconds and timezone-aware wall-clock deadlines survive JSON transport."""
    session = TimerSession.model_validate(
        {
            "user_id": USER_ID,
            "session_label": "Study",
            "phase": phase,
            "duration_seconds": 1800,
            "total_duration_seconds": 1800,
            "remaining_seconds": 0 if phase == "complete" else 1234.125,
            "end_date": "2026-10-21T14:30:00-04:00",
            "captured_at": "2026-10-21T14:00:00-04:00",
        }
    )
    assert TimerSession.model_validate_json(session.model_dump_json()) == session


@pytest.mark.parametrize(
    "field", ["duration_seconds", "total_duration_seconds", "remaining_seconds"]
)
@pytest.mark.parametrize("value", [-1, 6040, float("nan"), float("inf")])
def test_invalid_seconds(field: str, value: float) -> None:
    """Durations are finite and within the iOS 99:99 limit of 6039 seconds."""
    with pytest.raises(ValidationError):
        TimerSession.model_validate({"user_id": USER_ID, field: value})


@pytest.mark.parametrize(
    "changes",
    [
        {"remaining_seconds": 1801},
        {"phase": "running"},
        {"phase": "complete", "remaining_seconds": 1},
        {"phase": "unknown"},
        {"user_id": "invalid"},
        {"end_date": "2026-10-21T14:30:00"},
        {"captured_at": "2026-10-21T14:00:00"},
    ],
)
def test_invalid_snapshot(changes: dict[str, object]) -> None:
    """Reject invalid ownership, phases, naive timestamps, and inconsistent state."""
    with pytest.raises(ValidationError):
        TimerSession.model_validate({"user_id": USER_ID, **changes})


def test_maximum_and_zero_duration() -> None:
    """Both zero-length and maximum-length timers are supported by the app."""
    for seconds in (0, 6039):
        session = TimerSession(
            user_id=UUID(USER_ID),
            duration_seconds=seconds,
            total_duration_seconds=seconds,
            remaining_seconds=seconds,
        )
        assert session.remaining_seconds == seconds

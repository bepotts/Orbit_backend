"""User field validation and password handling tests."""

import pytest
from pydantic import ValidationError

from orbit_backend.models import User


def test_user() -> None:
    """Names are trimmed, email is validated, and password whitespace is preserved."""
    user = User.model_validate(
        {
            "first_name": " Ada ",
            "last_name": " Lovelace ",
            "email": "ada@example.com",
            "password": " secret password ",
        }
    )
    assert user.first_name == "Ada"
    assert user.last_name == "Lovelace"
    assert user.email == "ada@example.com"
    assert user.password.get_secret_value() == " secret password "
    assert "secret password" not in repr(user)
    assert "password" not in user.model_dump()
    assert "password" not in user.model_dump_json()


@pytest.mark.parametrize(
    ("field", "value"),
    [("first_name", "  "), ("last_name", ""), ("email", "invalid"), ("password", "")],
)
def test_invalid_user_field(field: str, value: str) -> None:
    """Empty names, invalid email, and empty passwords are rejected."""
    payload = {
        "first_name": "Ada",
        "last_name": "Lovelace",
        "email": "ada@example.com",
        "password": "test-password",
    }
    payload[field] = value
    with pytest.raises(ValidationError):
        User.model_validate(payload)


@pytest.mark.parametrize("field", ["first_name", "last_name", "email", "password"])
def test_required_user_field(field: str) -> None:
    """All four user fields are required."""
    payload = {
        "first_name": "Ada",
        "last_name": "Lovelace",
        "email": "ada@example.com",
        "password": "test-password",
    }
    del payload[field]
    with pytest.raises(ValidationError):
        User.model_validate(payload)

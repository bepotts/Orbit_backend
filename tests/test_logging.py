"""Verify rendered logs for both deployment environments."""

import json
import logging

import pytest
import structlog

from orbit_backend.logging import configure_logging
from orbit_backend.utils.enums import Environment


@pytest.mark.parametrize("environment", [Environment.DEVELOPMENT, Environment.PRODUCTION])
def test_rendering(environment: Environment, capsys: pytest.CaptureFixture[str]) -> None:
    """Application, server, and library events share rendering and severity filtering."""
    configure_logging(environment)
    configure_logging(environment)
    structlog.get_logger("orbit.test").info("timer.saved", session_id="123")
    logging.getLogger("uvicorn.error").warning("server ready")
    logging.getLogger("library").info("library ready")
    structlog.get_logger("orbit.test").debug("filtered")
    logging.getLogger("uvicorn.access").info("secret query")
    logging.getLogger("httpx").info("secret URL")
    try:
        raise ValueError("example failure")
    except ValueError:
        structlog.get_logger("orbit.test").exception("operation.failed")
    output = capsys.readouterr().out
    assert "filtered" not in output
    assert "secret" not in output
    assert "ValueError" in output
    if environment is Environment.PRODUCTION:
        entries = [json.loads(line) for line in output.splitlines()]
        assert len(entries) == 4
        assert entries[0]["session_id"] == "123"
        assert entries[0]["logger"] == "orbit.test"
        assert entries[1]["level"] == "warning"
        assert all(entry["timestamp"].endswith("Z") for entry in entries)
        assert "exception" in entries[3]
        assert "_record" not in output
    else:
        assert "timer.saved" in output
        assert "session_id=123" in output
        assert "library ready" in output
        assert "server ready" in output


def test_debug_level(capsys: pytest.CaptureFixture[str]) -> None:
    """Configured severity controls application events."""
    configure_logging(Environment.PRODUCTION, "DEBUG")
    structlog.get_logger("orbit.test").debug("visible")
    assert json.loads(capsys.readouterr().out)["event"] == "visible"

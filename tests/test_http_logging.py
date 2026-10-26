"""HTTP logging behavior, credential redaction, and streaming preservation."""

import asyncio
import logging

import pytest
from fastapi.testclient import TestClient
from starlette.types import Message, Receive, Scope, Send

from orbit_backend.logging import configure_logging
from orbit_backend.main import create_app
from orbit_backend.middleware.http_logging import (
    MAX_BODY_BYTES,
    HTTPLoggingMiddleware,
    payload_for_log,
    redact,
)
from orbit_backend.utils.enums import Environment


def test_redaction() -> None:
    """Nested credentials are redacted while ordinary data remains inspectable."""
    assert redact(
        {"first_name": "Ada", "data": [{"access_token": "secret", "API-Key": "key"}]}
    ) == {"first_name": "Ada", "data": [{"access_token": "[REDACTED]", "API-Key": "[REDACTED]"}]}


@pytest.mark.parametrize("body", [b"plain text", b"\xff", b"{invalid"])
def test_unstructured_payload(body: bytes) -> None:
    """Unstructured content is omitted rather than accidentally exposing credentials."""
    assert payload_for_log(bytearray(body), False) == "[OMITTED: non-JSON payload]"


def test_health_and_not_found(caplog: pytest.LogCaptureFixture) -> None:
    """Every HTTP exchange emits two correlated structured records."""
    configure_logging(Environment.DEVELOPMENT)
    caplog.set_level(logging.INFO, logger="orbit.http")
    with TestClient(create_app()) as client:
        assert client.get("/health?access_token=hidden&name=Ada").status_code == 200
        assert client.get("/missing").status_code == 404
    entries = [
        record.msg
        for record in caplog.records
        if record.name.endswith("orbit.http") and isinstance(record.msg, dict)
    ]
    assert len(entries) == 4
    assert entries[0]["request_id"] == entries[1]["request_id"]
    assert entries[0]["query"] == {"access_token": "[REDACTED]", "name": "Ada"}
    assert entries[0]["payload"] is None
    assert entries[1]["payload"] == {"status": "ok"}
    assert entries[3]["status"] == 404
    assert entries[1]["duration_ms"] >= 0
    assert "hidden" not in caplog.text


@pytest.mark.parametrize(
    "mode", ["json", "large", "failure", "websocket", "disconnect", "trailers"]
)
def test_asgi_messages(mode: str, caplog: pytest.LogCaptureFixture) -> None:
    """Streaming messages pass unchanged and failures still produce logging records."""
    configure_logging(Environment.DEVELOPMENT)
    caplog.set_level(logging.INFO, logger="orbit.http")
    request_data = b'{"password":"hidden","first_name":"Ada"}'
    response_data = b'{"refresh_token":"hidden","ok":true}'
    if mode == "large":
        request_data = response_data = b"x" * (MAX_BODY_BYTES + 10)
    incoming: list[Message] = [
        {"type": "http.request", "body": request_data[:10], "more_body": True},
        {"type": "http.request", "body": request_data[10:]},
    ]
    if mode == "disconnect":
        incoming = [{"type": "http.disconnect"}]
    outgoing: list[Message] = []

    async def receive() -> Message:
        return incoming.pop(0)

    async def send(message: Message) -> None:
        outgoing.append(message)

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        if mode == "websocket":
            await send({"type": "websocket.close"})
            return
        while incoming:
            await receive()
        if mode == "failure":
            raise RuntimeError("hidden")
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": response_data[:10], "more_body": True})
        await send({"type": "http.response.body", "body": response_data[10:]})
        if mode == "trailers":
            await send({"type": "http.response.trailers", "headers": []})

    scope: Scope = {
        "type": "websocket" if mode == "websocket" else "http",
        "method": "POST",
        "path": "/test",
    }
    run = HTTPLoggingMiddleware(app)(scope, receive, send)
    if mode == "failure":
        with pytest.raises(RuntimeError):
            asyncio.run(run)
    else:
        asyncio.run(run)
    entries = [
        record.msg
        for record in caplog.records
        if record.name.endswith("orbit.http") and isinstance(record.msg, dict)
    ]
    assert "hidden" not in caplog.text
    if mode == "websocket":
        assert entries == []
        assert outgoing == [{"type": "websocket.close"}]
    else:
        assert len(entries) == 2
        if mode == "failure":
            assert entries[1]["failed"] is True
            assert entries[1]["status"] == 500
        else:
            assert b"".join(message.get("body", b"") for message in outgoing) == response_data
            if mode == "large":
                assert "OMITTED" in entries[0]["payload"]
                assert "OMITTED" in entries[1]["payload"]
            elif mode == "json":
                assert entries[0]["payload"]["password"] == "[REDACTED]"
                assert entries[1]["payload"]["refresh_token"] == "[REDACTED]"

"""Bounded, credential-redacted HTTP request and response logging."""

import json
import logging
from time import perf_counter
from urllib.parse import parse_qsl
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("uvicorn.error.orbit.http")
MAX_BODY_BYTES = 16_384
SENSITIVE_PARTS = ("password", "token", "secret", "authorization", "cookie", "apikey", "credential")


def redact(value: object) -> object:
    """Recursively redact credential fields from JSON objects and arrays."""
    if isinstance(value, dict):
        return {
            key: "[REDACTED]"
            if any(
                part in str(key).lower().replace("_", "").replace("-", "")
                for part in SENSITIVE_PARTS
            )
            else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def payload_for_log(body: bytearray, oversized: bool) -> object:
    """Decode bounded JSON payloads; omit oversized or unstructured content."""
    if oversized:
        return "[OMITTED: payload exceeds 16384 bytes]"
    if not body:
        return None
    try:
        return redact(json.loads(body))
    except (ValueError, UnicodeDecodeError):
        return "[OMITTED: non-JSON payload]"


class HTTPLoggingMiddleware:
    """Observe ASGI messages without consuming bodies or buffering streamed responses."""

    def __init__(self, app: ASGIApp) -> None:
        """Store the next ASGI application."""
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Log each HTTP exchange with a correlation ID, payloads, and elapsed time."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = perf_counter()
        request_id = str(uuid4())
        request_body = bytearray()
        response_body = bytearray()
        request_size = 0
        response_size = 0
        status_code = 500
        failed = False

        async def logged_receive() -> Message:
            """Observe request chunks as the application consumes them."""
            nonlocal request_size
            message = await receive()
            if message["type"] == "http.request":
                chunk = message.get("body", b"")
                request_size += len(chunk)
                request_body.extend(chunk[: max(0, MAX_BODY_BYTES - len(request_body))])
            return message

        async def logged_send(message: Message) -> None:
            """Observe response chunks and forward them immediately."""
            nonlocal response_size, status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            elif message["type"] == "http.response.body":
                chunk = message.get("body", b"")
                response_size += len(chunk)
                response_body.extend(chunk[: max(0, MAX_BODY_BYTES - len(response_body))])
            await send(message)

        try:
            await self.app(scope, logged_receive, logged_send)
        except Exception:
            failed = True
            raise
        finally:
            common = {
                "request_id": request_id,
                "method": scope["method"],
                "path": scope["path"],
            }
            logger.info(
                "%s",
                json.dumps(
                    {
                        **common,
                        "event": "http.request",
                        "query": redact(
                            dict(
                                parse_qsl(
                                    scope.get("query_string", b"").decode("utf-8", errors="replace")
                                )
                            )
                        ),
                        "payload": payload_for_log(request_body, request_size > MAX_BODY_BYTES),
                    }
                ),
            )
            logger.info(
                "%s",
                json.dumps(
                    {
                        **common,
                        "event": "http.response",
                        "status": status_code,
                        "duration_ms": round((perf_counter() - started) * 1000, 2),
                        "failed": failed,
                        "payload": payload_for_log(response_body, response_size > MAX_BODY_BYTES),
                    }
                ),
            )

"""Application factory and initial HTTP endpoints."""

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Service liveness response."""

    status: Literal["ok"] = "ok"


class Message(BaseModel):
    """Validated JSON message accepted and returned by the example endpoint."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    message: str = Field(min_length=1, max_length=1000)


def create_app() -> FastAPI:
    """Create an independent application instance for serving or testing."""
    app = FastAPI(title="Orbit API", version="0.1.0")

    @app.get("/health", tags=["health"])
    async def health() -> HealthResponse:
        """Report whether the HTTP service is alive."""
        return HealthResponse()

    @app.post("/api/v1/echo", tags=["examples"])
    async def echo(payload: Message) -> Message:
        """Validate and return a JSON message without storing it."""
        return payload

    return app

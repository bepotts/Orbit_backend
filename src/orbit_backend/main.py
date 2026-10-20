"""Application factory and initial HTTP endpoints."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from orbit_backend.controllers.users import router as users_router
from orbit_backend.models import HealthResponse, Message


def create_app() -> FastAPI:
    """Create an independent application instance for serving or testing."""
    app = FastAPI(title="Orbit API", version="0.1.0")

    app.include_router(users_router)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        """Return validation details without echoing submitted passwords or other input."""
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {key: item[key] for key in ("type", "loc", "msg")} for item in error.errors()
                ]
            },
        )

    @app.get("/health", tags=["health"])
    async def health() -> HealthResponse:
        """Report whether the HTTP service is alive."""
        return HealthResponse()

    @app.post("/api/v1/echo", tags=["examples"])
    async def echo(payload: Message) -> Message:
        """Validate and return a JSON message without storing it."""
        return payload

    return app

"""Application factory and initial HTTP endpoints."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from orbit_backend.config import get_settings
from orbit_backend.controllers.sessions import router as sessions_router
from orbit_backend.controllers.users import router as users_router
from orbit_backend.middleware.http_logging import HTTPLoggingMiddleware
from orbit_backend.models import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Validate environment configuration before accepting requests."""
    get_settings()
    yield


def create_app() -> FastAPI:
    """Create an independent application instance for serving or testing."""
    app = FastAPI(title="Orbit API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(HTTPLoggingMiddleware)
    app.include_router(users_router)
    app.include_router(sessions_router)

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

    return app

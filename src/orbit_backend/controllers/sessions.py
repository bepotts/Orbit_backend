"""Supabase-managed sign-in, renewal, session identity, and sign-out."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from orbit_backend.controllers.users import login_user
from orbit_backend.database.supabase import SupabaseDependency
from orbit_backend.models import LoginResponse, RefreshSessionRequest, SessionUser
from orbit_backend.services.auth import auth_errors

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])
bearer = HTTPBearer(auto_error=False)


def require_bearer(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> str:
    """Require a bearer access token for current-session operations."""
    if credentials is None:
        raise HTTPException(401, "Bearer token required", headers={"WWW-Authenticate": "Bearer"})
    return credentials.credentials


AccessToken = Annotated[str, Depends(require_bearer)]

# Preserve /users/login while offering a resource-oriented session creation route.
router.add_api_route("", login_user, methods=["POST"], response_model=LoginResponse)


@router.post("/refresh", response_model=LoginResponse)
async def refresh_session(
    payload: RefreshSessionRequest, supabase: SupabaseDependency, response: Response
) -> LoginResponse:
    """Renew a Supabase session and return the rotated credentials."""
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    with auth_errors():
        result = await supabase.auth.refresh_session(payload.refresh_token.get_secret_value())
    if result.session is None:
        raise HTTPException(502, "Authentication returned an invalid response")
    session = result.session
    return LoginResponse(
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        token_type=session.token_type,
        expires_in=session.expires_in,
        expires_at=session.expires_at,
        user_id=session.user.id,
    )


@router.get("/current", response_model=SessionUser)
async def current_session(
    access_token: AccessToken, supabase: SupabaseDependency, response: Response
) -> SessionUser:
    """Verify the access token with Supabase and return its account identity."""
    response.headers["Cache-Control"] = "no-store"
    with auth_errors():
        result = await supabase.auth.get_user(access_token)
    if result is None or result.user is None:
        raise HTTPException(
            401, "Invalid or expired session", headers={"WWW-Authenticate": "Bearer"}
        )
    return SessionUser(id=result.user.id, email=result.user.email)


@router.delete("/current", status_code=204)
async def sign_out(access_token: AccessToken, supabase: SupabaseDependency) -> Response:
    """Revoke the current Supabase session's refresh tokens while preserving other devices."""
    with auth_errors():
        # The SDK calls /logout with this user's JWT; no service-role key is needed.
        await supabase.auth.admin.sign_out(access_token, scope="local")
    return Response(status_code=204, headers={"Cache-Control": "no-store"})

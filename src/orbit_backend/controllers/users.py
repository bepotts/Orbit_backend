"""User registration through Supabase Auth."""

from fastapi import APIRouter, HTTPException, Response
from httpx import RequestError
from pydantic import ValidationError
from supabase_auth.errors import AuthApiError, AuthError, AuthWeakPasswordError

from orbit_backend.database.supabase import SupabaseDependency
from orbit_backend.models import LoginRequest, LoginResponse, RegistrationResponse, User

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.post("", status_code=202, response_model=RegistrationResponse)
async def create_user(payload: User, supabase: SupabaseDependency) -> RegistrationResponse:
    """Submit user details to Supabase Auth, respecting email confirmation settings."""
    try:
        await supabase.auth.sign_up(
            {
                "email": str(payload.email),
                "password": payload.password.get_secret_value(),
                "options": {
                    "data": {"first_name": payload.first_name, "last_name": payload.last_name}
                },
            }
        )
    except AuthWeakPasswordError:
        raise HTTPException(400, "Password does not meet the required strength") from None
    except AuthApiError as error:
        if error.code in {"user_already_exists", "email_exists"}:
            return RegistrationResponse()
        if error.status == 429:
            raise HTTPException(429, "Too many registration attempts. Try again later.") from None
        if error.status >= 500:
            raise HTTPException(503, "Registration is temporarily unavailable") from None
        raise HTTPException(400, "Registration could not be completed") from None
    except ValidationError:
        raise HTTPException(502, "Registration returned an invalid response") from None
    except (AuthError, RequestError):
        raise HTTPException(503, "Registration is temporarily unavailable") from None

    return RegistrationResponse()


@router.post("/login", response_model=LoginResponse)
async def login_user(
    payload: LoginRequest, supabase: SupabaseDependency, response: Response
) -> LoginResponse:
    """Authenticate with Supabase and return a session without caching credentials."""
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    try:
        result = await supabase.auth.sign_in_with_password(
            {"email": str(payload.email), "password": payload.password.get_secret_value()}
        )
    except AuthApiError as error:
        if error.status == 429:
            raise HTTPException(429, "Too many login attempts. Try again later.") from None
        if error.status >= 500:
            raise HTTPException(503, "Login is temporarily unavailable") from None
        raise HTTPException(401, "Invalid email or password") from None
    except ValidationError:
        raise HTTPException(502, "Login returned an invalid response") from None
    except (AuthError, RequestError):
        raise HTTPException(503, "Login is temporarily unavailable") from None

    if result.session is None:
        raise HTTPException(502, "Login returned an invalid response")
    session = result.session
    return LoginResponse(
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        token_type=session.token_type,
        expires_in=session.expires_in,
        expires_at=session.expires_at,
        user_id=session.user.id,
    )

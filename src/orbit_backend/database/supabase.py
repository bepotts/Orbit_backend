"""Request-scoped asynchronous Supabase integration."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from httpx import AsyncClient as HTTPClient
from supabase import AsyncClient, AsyncClientOptions, acreate_client

from orbit_backend.config import Settings, get_settings


async def get_supabase(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncIterator[AsyncClient]:
    """Yield an isolated Supabase client and close its HTTP transport afterward.

    Session persistence and background refresh are disabled for server requests.
    Missing credentials only affect routes that depend on Supabase.
    """
    if settings.supabase_url is None or settings.supabase_key is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase is not configured",
        )

    async with HTTPClient(timeout=10) as transport:
        client = await acreate_client(
            str(settings.supabase_url),
            settings.supabase_key.get_secret_value(),
            options=AsyncClientOptions(
                persist_session=False,
                auto_refresh_token=False,
                httpx_client=transport,
            ),
        )
        yield client


SupabaseDependency = Annotated[AsyncClient, Depends(get_supabase)]

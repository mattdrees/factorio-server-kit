import logging

from fastapi import Header, HTTPException
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.config import settings

logger = logging.getLogger(__name__)

API_KEY = "Tanager"


async def verify_api_key(authorization: str = Header(None)):
    """Validate API key from Authorization header"""
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header"
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header format. Expected: Bearer <key>"
        )

    provided_key = authorization.split(" ", 1)[1]

    if provided_key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    return provided_key


def verify_task_oidc(authorization: str = Header(None)):
    """Verify a Google-signed OIDC token minted for the Cloud Tasks invoker
    service account.

    /internal/create lives on a publicly-invokable service, so it must be
    authenticated at the app layer: we require a valid ID token whose audience
    is this service's URL and whose (verified) email is the tasks invoker SA.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1]
    try:
        claims = id_token.verify_oauth2_token(
            token, google_requests.Request(), audience=settings.service_url
        )
    except Exception as e:
        raise HTTPException(status_code=403, detail=f"Invalid OIDC token: {e}")

    if not claims.get("email_verified") or claims.get("email") != settings.tasks_invoker_sa:
        raise HTTPException(
            status_code=403, detail="Token not issued to the tasks invoker service account"
        )

    return claims

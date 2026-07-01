import logging
from secrets import compare_digest

from fastapi import Header, HTTPException
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.config import settings

logger = logging.getLogger(__name__)


async def verify_api_key(authorization: str = Header(None)):
    """Validate the API key from the Authorization header against the value
    injected from Secret Manager (the API_KEY env var)."""
    if not settings.api_key:
        # Fail closed: the service is misconfigured if no key is set.
        logger.error("API_KEY is not configured; rejecting request")
        raise HTTPException(status_code=503, detail="Server auth not configured")

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

    if not compare_digest(provided_key, settings.api_key):
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

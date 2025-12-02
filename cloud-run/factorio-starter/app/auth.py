from fastapi import Header, HTTPException

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

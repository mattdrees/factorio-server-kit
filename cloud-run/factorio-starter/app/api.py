from fastapi import APIRouter, BackgroundTasks, Depends, Response
from fastapi.responses import JSONResponse
from datetime import datetime
from app.auth import verify_api_key
from app.gcp_state import get_server_status, has_running_or_creating_instance
from app.compute import create_server

router = APIRouter()


@router.post("/start")
def start_server(
    background_tasks: BackgroundTasks,
    _: str = Depends(verify_api_key)
):
    """Start server creation (async).

    Defined as a sync handler so the blocking GCP probe in
    has_running_or_creating_instance() runs in Starlette's threadpool instead
    of on the event loop, keeping the single worker responsive.
    """
    # Check GCP for existing instances
    if has_running_or_creating_instance():
        status = get_server_status()
        return JSONResponse(
            status_code=409,
            content={
                "status": "error",
                "message": f"Server already exists with status: {status['status']}",
                "details": status
            }
        )

    # Start creation in background
    background_tasks.add_task(create_server)

    # Return immediately
    return JSONResponse(
        status_code=202,
        content={
            "status": "creating",
            "message": "Server creation started",
            "started_at": datetime.utcnow().isoformat()
        }
    )


@router.get("/status")
def get_status(response: Response, _: str = Depends(verify_api_key)):
    """Get current server status by querying GCP resources.

    Sync handler: get_server_status() makes blocking GCP list calls and an
    RCON probe, so it must run in the threadpool, not on the event loop.
    """
    # Prevent caching to ensure fresh status
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return get_server_status()


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "factorio-starter",
        "version": "1.0.0"
    }

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from datetime import datetime
from app.auth import verify_api_key
from app.gcp_state import get_server_status, has_running_or_creating_instance
from app.compute import create_server_async

router = APIRouter()


@router.post("/start")
async def start_server(
    background_tasks: BackgroundTasks,
    _: str = Depends(verify_api_key)
):
    """Start server creation (async)"""
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
    background_tasks.add_task(create_server_async)

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
async def get_status(_: str = Depends(verify_api_key)):
    """Get current server status by querying GCP resources"""
    return get_server_status()


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "factorio-starter",
        "version": "1.0.0"
    }

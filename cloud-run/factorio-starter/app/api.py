import logging
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from datetime import datetime
from app.auth import verify_api_key, verify_task_oidc
from app.config import settings
from app.gcp_state import get_server_status, has_running_or_creating_instance
from app.compute import create_server
from app.tasks import enqueue_create_task

logger = logging.getLogger(__name__)

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

    # Kick off creation. With Cloud Tasks, enqueue a task that Cloud Run
    # delivers to /internal/create as a real request (CPU allocated for its
    # whole duration). Otherwise fall back to an in-process BackgroundTask,
    # which only survives while CPU is always-allocated.
    if settings.use_cloud_tasks:
        enqueue_create_task()
    else:
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


@router.post("/internal/create")
def internal_create(_: dict = Depends(verify_task_oidc)):
    """Cloud Tasks target: run the creation walk synchronously in this request.

    Only callable with an OIDC token from the tasks invoker SA (see
    verify_task_oidc). Returns non-2xx on failure so Cloud Tasks retries.
    """
    # At-least-once delivery + retries can redeliver this task. If a server is
    # already running or being created, treat it as done so we never end up with
    # two servers (also enforced by the queue's max_concurrent_dispatches=1).
    if has_running_or_creating_instance():
        logger.info("Server already running/creating; skipping duplicate create task")
        return {"status": "skipped", "reason": "server already exists"}

    try:
        create_server()
    except Exception as e:
        logger.error(f"create_server failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Server creation failed")

    return {"status": "created"}


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

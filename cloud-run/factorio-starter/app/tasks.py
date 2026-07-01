"""Cloud Tasks integration for deferring the server-creation walk.

/start enqueues a task here instead of running create_server() as an in-process
BackgroundTask. Cloud Tasks then delivers it to /internal/create as a normal
authenticated request, so the creation walk runs with CPU allocated for its full
duration even when Cloud Run CPU throttling is enabled.
"""
import logging

from google.cloud import tasks_v2

from app.config import settings

logger = logging.getLogger(__name__)


def enqueue_create_task() -> str:
    """Enqueue a task that POSTs to {SERVICE_URL}/internal/create.

    The task carries an OIDC token minted as the tasks invoker service account
    so /internal/create can authenticate the caller. This is a blocking call;
    invoke it from a sync (threadpool) handler. Returns the task name.
    """
    client = tasks_v2.CloudTasksClient()
    parent = client.queue_path(
        settings.google_cloud_project, settings.tasks_location, settings.tasks_queue
    )
    task = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": f"{settings.service_url}/internal/create",
            "headers": {"Content-Type": "application/json"},
            "body": b"{}",
            "oidc_token": {
                "service_account_email": settings.tasks_invoker_sa,
                "audience": settings.service_url,
            },
        }
    }
    response = client.create_task(parent=parent, task=task)
    logger.info(f"Enqueued create task: {response.name}")
    return response.name

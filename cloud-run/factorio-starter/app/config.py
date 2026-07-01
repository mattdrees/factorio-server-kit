from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    google_cloud_project: str = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    factorio_image_family: str = "packtorio"
    factorio_dns_zone: str = "factorio-server"
    factorio_dns_name: str = "factorio.menagerie.games"
    factorio_storage_bucket: str = ""
    port: int = 8080
    # Machine types to try (in order) when the instance template's default
    # machine type is unavailable. Tried after the template default, across a
    # region's zones, before moving on to the next region. Keep in sync with
    # lib/300.exports.sh.
    machine_type_fallbacks: List[str] = ["n2-standard-2", "n2d-standard-2", "e2-standard-2"]

    # Cloud Tasks migration: when true, /start enqueues a task that calls
    # /internal/create instead of running create_server() as an in-process
    # BackgroundTask. This lets the creation walk run inside an authenticated
    # request (CPU allocated for its full duration) so CPU throttling can be
    # enabled. All values below are injected by Terraform (see the Cloud Run
    # resource); defaults keep the legacy BackgroundTask path for local dev.
    use_cloud_tasks: bool = os.getenv("USE_CLOUD_TASKS", "false").lower() == "true"
    tasks_queue: str = os.getenv("TASKS_QUEUE", "factorio-create")
    tasks_location: str = os.getenv("TASKS_LOCATION", "")
    tasks_invoker_sa: str = os.getenv("TASKS_INVOKER_SA", "")
    # Base URL of this service; used as the task target host and OIDC audience.
    service_url: str = os.getenv("SERVICE_URL", "")

    def __init__(self):
        super().__init__()
        if not self.factorio_storage_bucket:
            self.factorio_storage_bucket = f"{self.google_cloud_project}-storage"


settings = Settings()

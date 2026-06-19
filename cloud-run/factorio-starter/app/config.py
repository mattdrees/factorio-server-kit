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
    machine_type_fallbacks: List[str] = ["n2-standard-2", "e2-standard-2"]

    def __init__(self):
        super().__init__()
        if not self.factorio_storage_bucket:
            self.factorio_storage_bucket = f"{self.google_cloud_project}-storage"


settings = Settings()

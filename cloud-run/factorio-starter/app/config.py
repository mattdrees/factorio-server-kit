from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    google_cloud_project: str = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    factorio_image_family: str = "packtorio"
    factorio_dns_zone: str = "factorio-server"
    factorio_dns_name: str = "factorio.menagerie.games"
    factorio_storage_bucket: str = ""
    port: int = 8080

    def __init__(self):
        super().__init__()
        if not self.factorio_storage_bucket:
            self.factorio_storage_bucket = f"{self.google_cloud_project}-storage"


settings = Settings()

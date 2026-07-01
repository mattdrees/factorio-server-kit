resource "google_storage_bucket" "storage" {
  name          = "${var.project_id}-storage"
  location      = local.default_region
  storage_class = "STANDARD"
}

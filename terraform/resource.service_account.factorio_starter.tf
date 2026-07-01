# Service account for Cloud Run factorio-starter service
resource "google_service_account" "factorio_starter" {
  account_id   = "factorio-starter"
  display_name = "Factorio Starter Service Account"
  description  = "Service account for Cloud Run service that starts Factorio servers"
}

# Compute Engine permissions - create/delete instances
resource "google_project_iam_member" "factorio_starter_compute" {
  project = var.project_id
  role    = "roles/compute.instanceAdmin.v1"
  member  = "serviceAccount:${google_service_account.factorio_starter.email}"
}

# Cloud DNS permissions - update DNS records
resource "google_project_iam_member" "factorio_starter_dns" {
  project = var.project_id
  role    = "roles/dns.admin"
  member  = "serviceAccount:${google_service_account.factorio_starter.email}"
}

# Cloud Storage permissions - read locations.json
resource "google_project_iam_member" "factorio_starter_storage" {
  project = var.project_id
  role    = "roles/storage.objectViewer"
  member  = "serviceAccount:${google_service_account.factorio_starter.email}"
}

# Cloud Logging permissions
resource "google_project_iam_member" "factorio_starter_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.factorio_starter.email}"
}

# Service Account User role - allows factorio-starter to use factorio-server service account
resource "google_service_account_iam_member" "factorio_starter_can_use_factorio_server" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/factorio-server@${var.project_id}.iam.gserviceaccount.com"
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.factorio_starter.email}"
}

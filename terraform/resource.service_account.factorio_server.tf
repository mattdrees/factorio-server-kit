# Service account for Factorio server VMs
resource "google_service_account" "factorio_server" {
  account_id   = "factorio-server"
  display_name = "Factorio Server Service Account"
  description  = "Service account for Factorio game server VMs"
}

# Grant necessary permissions to the service account
resource "google_project_iam_member" "factorio_server_storage" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.factorio_server.email}"
}

resource "google_project_iam_member" "factorio_server_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.factorio_server.email}"
}

resource "google_project_iam_member" "factorio_server_monitoring" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.factorio_server.email}"
}

# API key for the starter's web UI / REST API. Terraform manages the secret
# *container* and access only; the secret *value* is added out-of-band
# (`gcloud secrets versions add`) so it never lands in git or Terraform state.
# Rotate by adding a new version -- the Cloud Run env reads "latest".

resource "google_project_service" "secretmanager" {
  service            = "secretmanager.googleapis.com"
  disable_on_destroy = false
}

resource "google_secret_manager_secret" "factorio_starter_api_key" {
  secret_id = "factorio-starter-api-key"

  replication {
    auto {}
  }

  depends_on = [google_project_service.secretmanager]
}

# The Cloud Run runtime service account may read the key.
resource "google_secret_manager_secret_iam_member" "factorio_starter_api_key_accessor" {
  secret_id = google_secret_manager_secret.factorio_starter_api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.factorio_starter.email}"
}

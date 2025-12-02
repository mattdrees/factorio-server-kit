# Cloud Run service
resource "google_cloud_run_service" "factorio_starter" {
  name     = "factorio-starter"
  location = local.default_region

  template {
    spec {
      service_account_name = google_service_account.factorio_starter.email

      containers {
        image = "gcr.io/${var.project_id}/factorio-starter:latest"

        env {
          name  = "GOOGLE_CLOUD_PROJECT"
          value = var.project_id
        }

        env {
          name  = "FACTORIO_IMAGE_FAMILY"
          value = "packtorio"
        }

        env {
          name  = "FACTORIO_DNS_ZONE"
          value = "factorio-server"
        }

        env {
          name  = "FACTORIO_DNS_NAME"
          value = "factorio.menagerie.games"
        }

        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }
      }

      # Reduced timeout since we return immediately
      timeout_seconds = 60
    }

    metadata {
      annotations = {
        "autoscaling.knative.dev/maxScale"      = "1"
        "run.googleapis.com/cpu-throttling"     = "false"
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }

  depends_on = [google_project_service.cloudrun]
}

# Allow public access (secured by API key in application)
resource "google_cloud_run_service_iam_member" "factorio_starter_invoker" {
  service  = google_cloud_run_service.factorio_starter.name
  location = google_cloud_run_service.factorio_starter.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Output the service URL
output "factorio_starter_url" {
  value       = google_cloud_run_service.factorio_starter.status[0].url
  description = "URL of the factorio-starter Cloud Run service"
}

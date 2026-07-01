# Cloud Run service
resource "google_cloud_run_service" "factorio_starter" {
  name     = "factorio-starter"
  location = local.default_region

  template {
    spec {
      service_account_name = google_service_account.factorio_starter.email

      containers {
        image = local.factorio_starter_image

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

        # Cloud Tasks migration: enqueue creation instead of running it as an
        # in-process BackgroundTask.
        env {
          name  = "USE_CLOUD_TASKS"
          value = "true"
        }

        env {
          name  = "TASKS_QUEUE"
          value = google_cloud_tasks_queue.factorio_create.name
        }

        env {
          name  = "TASKS_LOCATION"
          value = google_cloud_tasks_queue.factorio_create.location
        }

        env {
          name  = "TASKS_INVOKER_SA"
          value = google_service_account.factorio_starter_tasks.email
        }

        env {
          name  = "SERVICE_URL"
          value = local.factorio_starter_url
        }

        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }
      }

      # /internal/create runs the creation walk synchronously within the
      # request, so the timeout must cover the worst-case walk (keep the
      # gunicorn --timeout in the Dockerfile >= this value).
      timeout_seconds = 900
    }

    metadata {
      annotations = {
        "autoscaling.knative.dev/maxScale" = "1"
        # NOTE: still always-allocated. Flip to "true" (request-based CPU) only
        # AFTER verifying the Cloud Tasks path works end-to-end -- that is the
        # cost-saving payoff of this migration and the final rollout step.
        "run.googleapis.com/cpu-throttling" = "false"
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

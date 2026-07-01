# Cloud Tasks decouples the long-running server-creation walk from the /start
# request: /start enqueues a task, and the queue delivers it to
# /internal/create as an authenticated request that runs create_server() with
# CPU allocated for its full duration. This replaces the in-process
# BackgroundTask, which only survives while Cloud Run CPU is always-allocated.

resource "google_project_service" "cloudtasks" {
  service            = "cloudtasks.googleapis.com"
  disable_on_destroy = false
}

resource "google_cloud_tasks_queue" "factorio_create" {
  name     = "factorio-create"
  location = local.default_region

  rate_limits {
    # One creation in flight at a time -- belt-and-suspenders with the
    # has_running_or_creating_instance() guard in the app.
    max_concurrent_dispatches = 1
    max_dispatches_per_second = 1
  }

  retry_config {
    max_attempts  = 3
    min_backoff   = "10s"
    max_backoff   = "60s"
    max_doublings = 2
  }

  depends_on = [google_project_service.cloudtasks]
}

# Identity Cloud Tasks uses to mint the OIDC token when dispatching to
# /internal/create; the app verifies the caller is this account.
resource "google_service_account" "factorio_starter_tasks" {
  account_id   = "factorio-starter-tasks"
  display_name = "Factorio Starter Tasks Invoker"
  description  = "OIDC identity Cloud Tasks uses to call factorio-starter /internal/create"
}

# Lets the invoker SA call the Cloud Run service. The service is public today
# and /internal/create is enforced at the app layer, but this future-proofs
# locking the service down to authenticated-only.
resource "google_cloud_run_service_iam_member" "factorio_starter_tasks_invoker" {
  service  = google_cloud_run_service.factorio_starter.name
  location = google_cloud_run_service.factorio_starter.location
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.factorio_starter_tasks.email}"
}

# The service SA (which creates tasks) may enqueue onto the queue...
resource "google_cloud_tasks_queue_iam_member" "factorio_starter_enqueue" {
  name     = google_cloud_tasks_queue.factorio_create.name
  location = google_cloud_tasks_queue.factorio_create.location
  role     = "roles/cloudtasks.enqueuer"
  member   = "serviceAccount:${google_service_account.factorio_starter.email}"
}

# ...and may mint OIDC tokens as the invoker SA when attaching them to tasks.
resource "google_service_account_iam_member" "factorio_starter_act_as_tasks_sa" {
  service_account_id = google_service_account.factorio_starter_tasks.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.factorio_starter.email}"
}

locals {
  locations_json = jsondecode(file("${path.module}/../lib/locations.json"))

  default_location = [for loc in local.locations_json : loc if lookup(loc, "default", false) == true][0]

  # Extract region from the primary zone by removing last 2 characters (e.g., "europe-west2-c" -> "europe-west2")
  default_region = substr(local.default_location.zones[0], 0, length(local.default_location.zones[0]) - 2)

  # Image deploy.sh passes the built digest; fall back to the floating tag.
  factorio_starter_image = var.factorio_starter_image != "" ? var.factorio_starter_image : "gcr.io/${var.project_id}/factorio-starter:latest"
}

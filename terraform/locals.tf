locals {
  locations_json = jsondecode(file("${path.module}/../lib/locations.json"))

  default_location = [for loc in local.locations_json : loc if lookup(loc, "default", false) == true][0]

  # Extract region from zone by removing last 2 characters (e.g., "europe-west2-c" -> "europe-west2")
  default_region = substr(local.default_location.zone, 0, length(local.default_location.zone) - 2)
}

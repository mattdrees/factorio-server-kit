# One saves bucket per location, keyed by location name. Using for_each (rather
# than count) keeps each bucket's address stable when locations are added or
# removed, so dropping a location only destroys that location's bucket instead of
# shifting positional indices and recreating others.
resource "google_storage_bucket" "saves" {
  for_each = { for loc in local.locations_json : loc.location => loc }

  name = format("%s-saves-%s", var.project_id, each.value.location)

  # Co-locate the bucket with the location's primary zone's region.
  location = substr(each.value.zones[0], 0, length(each.value.zones[0]) - 2)
}

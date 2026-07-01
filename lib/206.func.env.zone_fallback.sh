#!/usr/bin/env bash
set -euo pipefail

# Echoes one line per location (each location is a single region), with that
# location's zones space-separated on the line. The selected location comes first
# (so we stay in-region for the cheapest, lowest-latency fallback), followed by
# every other location as a last resort for whole-region shortages. Callers
# iterate a whole region's zones together so they can exhaust the region (and
# downgrade machine types within it) before moving on.
#
# Example output (selected = iowa):
#   us-central1-c us-central1-a us-central1-b us-central1-f
#   us-west2-a us-west2-c
#   us-east1-d us-east1-b us-east1-c
#
# Arguments:
# - 1: selected location name (a "location" key from lib/locations.json)
function factorio::env::zone_fallback_groups() {
  local selected_location="${1:?}"
  local locations_json="${FACTORIO_ROOT:?}/lib/locations.json"

  jq --raw-output --arg selected "$selected_location" '
    (map(select(.location == $selected)) + map(select(.location != $selected)))
    | .[] | .zones | join(" ")
  ' "$locations_json"
}

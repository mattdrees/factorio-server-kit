#!/usr/bin/env bash
set -euo pipefail

# Arguments:
# - 1: (optional) name filter passed to 'gcloud compute instances list'
# - 2: (optional) instance name to skip, e.g. one we just created and want to keep
function factorio::vm::delete_instances() {
  local delete_instances i
  local exclude_name="${2:-}"
  local gcloud_list_args=(
    "--format=json"
    compute
    instances
    list
  )

  if [[ -n ${1:-} ]]; then
    gcloud_list_args+=("--filter=name:$1")
  fi

  echo -n "Listing instances: gcloud "
  echo "${gcloud_list_args[@]}"
  delete_instances=$(gcloud "${gcloud_list_args[@]}")
  for_loop_limit=$(jq length <<< "$delete_instances")

  for ((i = 0; i < for_loop_limit; i += 1)); do
    local name zone
    name=$(jq --raw-output ".[$i].name" <<< "$delete_instances")

    if [[ -n $exclude_name && $name == "$exclude_name" ]]; then
      continue
    fi

    jq_output=$(jq --raw-output ".[$i].zone" <<< "$delete_instances")
    zone=$(basename "$jq_output")

    local gcloud_delete_args=(
      "--format=json"
      compute
      instances
      delete
      --quiet
      "--zone=$zone"
      "$name"
    )

    echo -n "Deleting instance: gcloud "
    echo "${gcloud_delete_args[@]}"
    gcloud "${gcloud_delete_args[@]}"
  done
}

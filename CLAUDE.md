# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Factorio Server Kit automates running a Factorio game server on Google Cloud Platform using preemptible VMs to minimize costs. The project uses Bash scripts, Terraform for infrastructure-as-code, Cloud Build pipelines with Packer for VM image creation, and Go-based Cloud Functions for automated cleanup.

## Key Architecture Components

### 1. Location Management System
- **lib/locations.json**: Defines all valid GCP zones and their friendly names (london, sydney, tokyo, etc.)
- One location must be marked with `"default": true`
- **lib/300.exports.sh**: Parses locations.json and exports the `FACTORIO_SERVER_LOCATIONS` associative array mapping location names to zones
- All scripts source this to understand available deployment locations

### 2. Library System (lib/)
All main scripts source the entire lib/ directory in numeric order:
- **100.prereqs.sh**: Validates required tools (gcloud, jq) and environment variables
- **200-205 series**: Utility functions (password generation, array joining, VM deletion, DNS updates, location setting)
- **300.exports.sh**: Sets up environment variables and exports (FACTORIO_DNS_NAME, FACTORIO_IMAGE_FAMILY, FACTORIO_LOCATION, etc.)
- **400.terraform.sh**: Terraform-related functions

Scripts must set `FACTORIO_ROOT` to the git repository root, then source all lib/*.sh files before executing main logic.

### 3. VM Image Creation Pipeline
Two-stage Cloud Build process:
1. **cloud-build/0-packer/**: Creates a Docker image containing Packer
2. **cloud-build/1-factorio-server/**: Uses the Packer Docker image to build a GCE VM image with:
   - Docker runtime
   - Factorio server container (factoriotools/factorio)
   - Optional Graftorio monitoring (Grafana + Prometheus)
   - goppuku binary for auto-shutdown when player count stays at zero

The **build.sh** script handles the build workflow, syncing lib/ files to Cloud Storage, submitting the Cloud Build, and pruning old images.

### 4. Cloud Functions (functions/)
Go-based Cloud Functions using the legacy event-driven model:
- **cleanup.go**: Entry point for cleanup function triggered by Cloud Scheduler via Pub/Sub
- **instances.go**: Deletes terminated VMs matching the naming pattern used by roll-vm.sh
- **disks.go**: Cleans up orphaned disks
- **locations.go**: Fetches location data from Cloud Storage

The cleanup function runs periodically to remove terminated instances across all zones defined in locations.json.

### 5. Terraform Infrastructure (terraform/)
Provisions:
- Cloud Pub/Sub topic: `cleanup-instances`
- Cloud Scheduler job: triggers cleanup function periodically
- Cloud Storage buckets for saves and general storage
- Note: Uses remote state stored in gs://<project>-tfstate bucket (created by init.sh)

Scripts: **init.sh** (creates state bucket + terraform init), **plan.sh**, **apply.sh**

## Common Development Commands

### Building and Deploying

```bash
# Set your GCP project
export CLOUDSDK_CORE_PROJECT=my-factorio-server-kit

# Initialize Terraform infrastructure
cd terraform
./init.sh
./plan.sh
./apply.sh

# Build Packer Docker image (do this first)
cd cloud-build/0-packer
# Follow instructions in that directory's README

# Build Factorio server VM image
cd cloud-build/1-factorio-server
./build.sh                    # Standard build
./build.sh --graftorio        # Include Graftorio monitoring

# Deploy a server
cd scripts
./roll-vm.sh                          # Deploy to default location
./roll-vm.sh --sydney                 # Deploy to specific location
./roll-vm.sh --machine-type=e2-medium # Specify machine type
./roll-vm.sh --logs                   # Open Stackdriver logs after creation

# Delete running servers
./delete-vm.sh                # Delete all VMs
./delete-vm.sh factorio-*     # Delete VMs matching pattern
```

### Working with Cloud Functions

```bash
cd functions

# Deploy the cleanup function
./deploy.sh

# The function is triggered by Cloud Scheduler (configured in Terraform)
# Manual testing: publish message to cleanup-instances Pub/Sub topic
```

### Linting and Testing

```bash
# Lint all Bash scripts (uses shfmt, shellharden, shellcheck)
./lint-bash.sh

# This runs automatically via lefthook on pre-push
```

## Important Patterns and Conventions

### Bash Script Structure
Every main script follows this pattern:
```bash
#!/usr/bin/env bash
set -euo pipefail

FACTORIO_ROOT="$(cd "$(dirname "${BASH_SOURCE[-1]}")" && git rev-parse --show-toplevel)"
readonly FACTORIO_ROOT

# Source all library functions
for lib in "$FACTORIO_ROOT"/lib/*.sh; do
  source "$lib"
done

# Script logic here...
```

### Environment Variables
Critical variables exported by lib/300.exports.sh:
- `CLOUDSDK_CORE_PROJECT`: GCP project ID (must be set by user)
- `CLOUDSDK_COMPUTE_REGION`: Set dynamically based on zone
- `CLOUDSDK_COMPUTE_ZONE`: Set dynamically based on location
- `FACTORIO_SERVER_LOCATIONS`: Associative array of location→zone mappings
- `FACTORIO_IMAGE_FAMILY`: "packtorio"
- `FACTORIO_IMAGE_NAME`: Generated with timestamp
- `FACTORIO_DNS_NAME`: factorio.menagerie.games
- `FACTORIO_LOCATION`: Default location from locations.json
- `FACTORIO_PACKER_VERSION` and `FACTORIO_PACKER_VERSION_SHA256SUM`

### VM Naming Convention
VMs are named: `<server-type>-<location>-<timestamp>`
Example: `factorio-sydney-20231115-143022`

This pattern is used by both roll-vm.sh (creation) and the cleanup Cloud Function (deletion).

### Google Cloud SDK Usage
Scripts build gcloud command arrays and echo them before execution for transparency:
```bash
gcloud_args=(--format json compute instances list)
echo -n "Listing instances: gcloud "
echo "${gcloud_args[@]}"
result=$(gcloud "${gcloud_args[@]}")
```

### gsutil Considerations
When running locally (potentially from Mac), use `-o "GSUtil:parallel_process_count=1"` to avoid resource issues.

## Configuration Files

- **config/map-gen-settings.json**: Map generation settings
- **config/map-settings.json**: Gameplay settings
- **config/server-settings.json**: Server configuration
- **config/server-adminlist.json**: Admin users
- **config/server-whitelist.json**: Whitelisted users
- **mods/mod-list.json**: Enabled mods list

These can be generated from a map exchange string in-game.

## Dependencies and Tooling

Required external tools:
- **Google Cloud SDK** (gcloud)
- **jq** (JSON parsing)
- **Terraform** (infrastructure)
- **shfmt** (Bash formatting)
- **shellharden** (Bash security)
- **shellcheck** (Bash linting)

Go dependencies managed in functions/go.mod (Go Cloud Functions).

## Notes on Cost Optimization

- Uses **preemptible VMs** to reduce costs significantly
- **goppuku** service auto-shuts down the server after 15 minutes with zero players
- Cleanup function removes terminated instances to avoid storage costs
- Cloud Scheduler triggers periodic cleanup to minimize resource usage

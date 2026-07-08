# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Factorio Server Kit automates running a Factorio game server on Google Cloud Platform. Costs are kept
low by an auto-shutdown service (goppuku) that stops the server when it's empty. There are two ways to
launch a server:

1. **From the command line** — the `scripts/roll-vm.sh` Bash script.
2. **From a browser** — a Cloud Run "starter" service (`cloud-run/factorio-starter/`, a Python
   FastAPI app with a small web UI and REST API).

Both paths create a VM from the most recent `packtorio-*` instance template. Supporting pieces:
Terraform for infrastructure-as-code, Cloud Build pipelines with Packer for VM image creation, and a
Go-based Cloud Function for automated cleanup of terminated instances.

## Key Architecture Components

### 1. Location Management System
- **lib/locations.json**: An array of locations. Each entry has a friendly `location` name (iowa,
  losangeles, southcarolina, …) and a `zones` array. **The schema uses `zones` (an array), not a
  single `zone` string.** The first zone in each array is the primary/preferred zone; the rest are
  in-region fallbacks. Exactly one location must be marked with `"default": true`.
- **lib/300.exports.sh**: Parses locations.json and exports the `FACTORIO_SERVER_LOCATIONS`
  associative array mapping each location name to its **primary** zone.
- **lib/206.func.env.zone_fallback.sh**: Provides the zone/machine-type fallback walk used when a zone
  is out of capacity (`ZONE_RESOURCE_POOL_EXHAUSTED`).
- All scripts source these to understand available deployment locations and fallback order.

### 2. Library System (lib/)
All main scripts source the entire lib/ directory in numeric order:
- **100.prereqs.sh**: Validates required tools (gcloud, jq) and environment variables
- **200–205 series**: Utility functions (password generation, array joining, VM deletion, DNS
  updates, location setting, run-date formatting)
- **206.func.env.zone_fallback.sh**: Zone + machine-type fallback helpers
- **300.exports.sh**: Sets up environment variables and exports (FACTORIO_DNS_NAME,
  FACTORIO_IMAGE_FAMILY, FACTORIO_LOCATION, FACTORIO_MACHINE_TYPE_FALLBACKS, etc.)
- **400.terraform.sh**: Terraform-related functions

Scripts must set `FACTORIO_ROOT` to the git repository root, then source all lib/*.sh files before
executing main logic.

### 3. Cloud Run Starter Service (cloud-run/factorio-starter/)
A Python **FastAPI** app deployed to Cloud Run that lets players start a server without a local
toolchain. Key points:
- **Endpoints**: `/` (web UI), `POST /start`, `GET /status`, `GET /health`, and `POST
  /internal/create`.
- **Deferred creation**: `POST /start` returns `202` immediately and enqueues a **Cloud Tasks** job.
  Cloud Tasks then calls `POST /internal/create` (authenticated with an OIDC token) so the slow
  VM-creation walk runs inside a request that has CPU allocated for its full duration — necessary
  because Cloud Run CPU throttling is enabled (request-based billing). There is no in-process
  BackgroundTask path.
- **Stateless status**: `app/gcp_state.py` derives status by inspecting live GCP resources plus an
  RCON probe, rather than storing state.
- **Auth**: `app/auth.py` validates the API key (stored in Secret Manager as
  `factorio-starter-api-key`, injected as the `API_KEY` env var) and verifies Cloud Tasks OIDC
  tokens for `/internal/create`.
- **Single server**: only one server is allowed at a time (cost protection).
- **Layout**: `main.py` (entry point), `app/api.py` (routes), `app/tasks.py` (Cloud Tasks enqueue),
  `app/compute.py` (GCE operations), `app/dns.py` (Cloud DNS updates), `static/index.html` (web UI).
- **deploy.sh** builds the container image **and runs `terraform apply`**, then prints the service URL.

### 4. VM Image Creation Pipeline
Two-stage Cloud Build process:
1. **cloud-build/0-packer/**: Creates a Docker image containing Packer
2. **cloud-build/1-factorio-server/**: Uses the Packer Docker image to build a GCE VM image with:
   - Docker runtime
   - Factorio server container (factoriotools/factorio)
   - Optional Graftorio monitoring (Grafana + Prometheus)
   - goppuku binary for auto-shutdown when player count stays at zero

The **build.sh** script handles the build workflow, syncing lib/ files to Cloud Storage, submitting
the Cloud Build, and pruning old images. Use `--graftorio` to bake in monitoring.

### 5. Cloud Functions (functions/)
Go-based Cloud Function deployed as a **gen2** function (see `functions/deploy.sh`, `--gen2`, runtime
`go126`), triggered by Cloud Scheduler via Pub/Sub:
- **cleanup.go**: Entry point for the cleanup function
- **instances.go**: Deletes terminated VMs matching the naming pattern used by roll-vm.sh (iterating
  every zone in every location's `zones` array)
- **disks.go**: Cleans up orphaned disks
- **locations.go**: Fetches location data from Cloud Storage

`deploy.sh` discovers the exported functions via `go doc`, cleans up any copies deployed in other
regions, then deploys each one.

### 6. Terraform Infrastructure (terraform/)
Split into one `resource.*.tf` file per concern. Provisions:
- Cloud Pub/Sub topic + Cloud Scheduler job for the cleanup function
- Cloud Run service and Cloud Tasks queue for the factorio-starter
- Secret Manager secret (`factorio-starter-api-key`)
- Service accounts (factorio server VM, factorio-starter) and required project service enablement
- Firewall rule for the Factorio port
- Cloud Storage buckets: `<project>-saves-<location>` (keyed with `for_each` off locations.json) and
  `<project>-storage`
- Note: uses remote state stored in `gs://<project>-tfstate` (created by init.sh)

Scripts: **init.sh** (creates state bucket + terraform init), **plan.sh**, **apply.sh**.

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
./build.sh                    # follow the directory's README

# Build Factorio server VM image
cd cloud-build/1-factorio-server
./build.sh                    # Standard build
./build.sh --graftorio        # Include Graftorio monitoring

# Deploy the Cloud Run starter (optional; builds container + terraform apply)
cd cloud-run/factorio-starter
./deploy.sh

# Deploy a server from the CLI
cd scripts
./roll-vm.sh                          # Deploy to default location
./roll-vm.sh --sydney                 # Deploy to specific location
./roll-vm.sh --machine-type=e2-medium # Specify machine type
./roll-vm.sh --logs                   # Open Cloud Logging after creation
./roll-vm.sh --help                   # Full option list including all locations

# Delete running servers
./delete-vm.sh                # Delete all VMs
./delete-vm.sh 'factorio-*'   # Delete VMs matching pattern
```

### Working with Cloud Functions

```bash
cd functions

# Deploy the cleanup function(s)
./deploy.sh

# Triggered by Cloud Scheduler (configured in Terraform).
# Manual testing: publish a message to the cleanup Pub/Sub topic.
```

### Working with the Cloud Run Starter

```bash
cd cloud-run/factorio-starter

# Local development
export GOOGLE_CLOUD_PROJECT=your-project-id
gcloud auth application-default login
pip install -r requirements.txt
uvicorn main:app --reload --port 8080

# Against a deployed instance (API key required for /start and /status)
curl -X POST "$STARTER_URL/start"  -H "Authorization: Bearer <your-api-key>"
curl -X GET  "$STARTER_URL/status" -H "Authorization: Bearer <your-api-key>"
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
- `FACTORIO_SERVER_LOCATIONS`: Associative array of location→primary-zone mappings
- `FACTORIO_IMAGE_FAMILY`: "packtorio"
- `FACTORIO_IMAGE_NAME`: Generated with timestamp
- `FACTORIO_DNS_NAME`: factorio.menagerie.games
- `FACTORIO_LOCATION`: Default location from locations.json
- `FACTORIO_MACHINE_TYPE_FALLBACKS`: Alternate machine types tried on capacity stockout
- `FACTORIO_PACKER_VERSION` and `FACTORIO_PACKER_VERSION_SHA256SUM`

### Zone and Machine-Type Fallback
When a zone is out of capacity, both the CLI (`roll-vm.sh`) and the web starter walk fallbacks with a
**"stay in region, then downgrade"** strategy: for each region (selected location first, then the
others), exhaust its zones with the instance template's default machine type (`c2d-standard-2`), then
downgrade through `FACTORIO_MACHINE_TYPE_FALLBACKS` across those same zones, before moving to the next
region. The machine-type list lives in **lib/300.exports.sh** and
**cloud-run/factorio-starter/app/config.py** — keep them in sync.

### VM Naming Convention
VMs are named: `<server-type>-<region>-<timestamp>`
Example: `factorio-us-east1-20231115-143022`

The `<region>` segment is the GCP region the VM is **actually** created in (derived by
stripping the zone suffix, e.g. `us-west2-a` → `us-west2`), determined only after the
capacity-fallback walk lands. It is NOT the requested location name — fallback can cross
regions, so naming after the requested location would misreport where the VM lives.

Because of this, the cleanup Cloud Function (`functions/instances.go`) must match on the
generic `factorio-*` prefix across every zone, **not** `factorio-<location>-*` scoped to a
location's own zones — a cross-region fallback VM would otherwise never match and never be
cleaned up. Both roll-vm.sh (creation) and the cleanup function follow this.

### Google Cloud SDK Usage
Scripts build gcloud command arrays and echo them before execution for transparency:
```bash
gcloud_args=(--format json compute instances list)
echo -n "Listing instances: gcloud "
echo "${gcloud_args[@]}"
result=$(gcloud "${gcloud_args[@]}")
```

### gsutil Considerations
When running locally (potentially from Mac), use `-o "GSUtil:parallel_process_count=1"` to avoid
resource issues.

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

Go dependencies are managed in functions/go.mod (Go Cloud Function). The Cloud Run starter's Python
dependencies are in cloud-run/factorio-starter/requirements.txt.

## Notes on Cost Optimization

- **goppuku** auto-shuts down the server after 15 minutes with zero players — the primary cost lever,
  since compute is billed only while the server is up. (Servers are standard on-demand `c2d-standard-2`
  VMs, not Spot/preemptible; the instance template in `cloud-build/1-factorio-server/cloudbuild.yaml`
  uses `--maintenance-policy=MIGRATE`.)
- The Cloud Run starter uses **request-based (CPU-throttled) billing** and defers slow work to Cloud
  Tasks, so CPU is billed only while a request is in flight.
- The **cleanup Cloud Function** removes terminated instances and orphaned disks to avoid storage
  costs; Cloud Scheduler triggers it periodically.

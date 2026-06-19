# Rollout: zone + machine-type fallback

One-time deployment runbook for the zone/region + machine-type fallback change
(new `locations.json` schema, Dallas dropped). Run on the machine that has the
Terraform state and gcloud auth for the Factorio GCP project.

Once this has been applied successfully, this file can be deleted.

## What changed (why each step is needed)

- `lib/locations.json` schema: `zone` (string) → `zones` (array); Dallas removed.
- Consumers updated: `lib/` exports + `roll-vm.sh`, the Go cleanup function, the
  Cloud Run starter (Python), the VM `startup.sh`/`shutdown.sh`, and Terraform.
- Terraform saves buckets converted from `count` to `for_each` (so dropping a
  location no longer shifts indices and recreates other buckets).

## Prerequisites

```bash
# The project that hit ZONE_RESOURCE_POOL_EXHAUSTED:
export CLOUDSDK_CORE_PROJECT=silken-gadget-435515-i7
gcloud config set project "$CLOUDSDK_CORE_PROJECT"
gcloud auth list   # confirm the right account is active
```

## Step 1 — Terraform: migrate saves-bucket state, then apply

The saves buckets moved from `count`-indexed to `for_each`-keyed. Without a state
migration, Terraform would try to destroy & recreate every bucket. Buckets have
no `force_destroy`, so a non-empty bucket destroy *errors* rather than deleting
saves — but do the migration to get a clean plan.

```bash
cd terraform

# 1a. Confirm current (count-based) indices before moving. Original locations.json
#     order was iowa, losangeles, dallas, southcarolina -> [0],[1],[2],[3].
terraform state list | grep 'google_storage_bucket.saves'
terraform state show 'google_storage_bucket.saves[0]' | grep -E 'name|location'  # expect -saves-iowa
terraform state show 'google_storage_bucket.saves[1]' | grep -E 'name|location'  # expect -saves-losangeles
terraform state show 'google_storage_bucket.saves[2]' | grep -E 'name|location'  # expect -saves-dallas
terraform state show 'google_storage_bucket.saves[3]' | grep -E 'name|location'  # expect -saves-southcarolina

# 1b. Move the kept buckets to their new for_each keys (adjust indices if 1a differs).
terraform state mv 'google_storage_bucket.saves[0]' 'google_storage_bucket.saves["iowa"]'
terraform state mv 'google_storage_bucket.saves[1]' 'google_storage_bucket.saves["losangeles"]'
terraform state mv 'google_storage_bucket.saves[3]' 'google_storage_bucket.saves["southcarolina"]'

# 1c. saves[2] (dallas) is intentionally left in state. The plan below will
#     destroy the empty -saves-dallas bucket (OK'd). If that destroy ever fails
#     because the bucket is non-empty, either empty it or run:
#       terraform state rm 'google_storage_bucket.saves[2]'   # keep bucket, stop managing it

# 1d. Review the plan. It should show ONLY: destroy -saves-dallas. No changes to
#     iowa / losangeles / southcarolina buckets.
./plan.sh

# 1e. Apply.
./apply.sh
cd ..
```

## Step 2 — Rebuild the VM image (also uploads the new locations.json)

`startup.sh` / `shutdown.sh` changed (zone→location lookup), and `build.sh` also
rsyncs `lib/*.json` (incl. the new `locations.json`) to
`gs://$CLOUDSDK_CORE_PROJECT-storage/lib/`, which the cleanup function, the Cloud
Run starter, and VM startup all read at runtime.

```bash
cd cloud-build/1-factorio-server
./build.sh                 # add --graftorio if you normally build with monitoring
cd ../..
```

If you want to push the new `locations.json` to GCS *without* a full image
rebuild (e.g. to update the running cleanup function / starter immediately):

```bash
gsutil -m -o "GSUtil:parallel_process_count=1" rsync -P \
  -x '^.*\.sh$|^\.gitignore$' \
  lib/ "gs://$CLOUDSDK_CORE_PROJECT-storage/lib/"
```

## Step 3 — Redeploy the cleanup Cloud Function (Go)

`functions/cleanup.go` + `instances.go` changed (iterate `zones[]`).

```bash
cd functions
./deploy.sh
cd ..
```

## Step 4 — Redeploy the Cloud Run starter (Python)

`cloud-run/factorio-starter/app/*` changed (zone + machine-type fallback). Note:
this `deploy.sh` builds the container **and runs `terraform plan`/`apply`**. After
Step 1 that apply is a no-op for the buckets.

```bash
cd cloud-run/factorio-starter
./deploy.sh
cd ../..
```

## Step 5 — Verify

```bash
# CLI path: roll a server. With us-central1-c exhausted it should fall through
# zones (then downgrade machine type within a zone) until one succeeds.
cd scripts
./roll-vm.sh
cd ..

# Web path: start via the Cloud Run service and watch status flip to running.
SERVICE_URL=$(gcloud run services describe factorio-starter \
  --region="$(gcloud run services list --format='value(REGION)' --filter='factorio-starter' | head -1)" \
  --format='value(status.url)')
curl -X POST "$SERVICE_URL/start"  -H 'Authorization: Bearer Tanager'
curl -X GET  "$SERVICE_URL/status" -H 'Authorization: Bearer Tanager'
```

## Notes

- **Fallback order (CLI & web) — "stay in region, then downgrade":** for each
  region (selected location first, then others), exhaust its zones with the
  template default machine type (`c2d-standard-2`), then downgrade the machine
  type (`n2-standard-2`, then `e2-standard-2`) across those same zones, before
  moving to the next region. E.g. for `iowa`:
  `us-central1-{c,a,b,f}`×c2d → ×n2 → ×e2 → then `us-west2` → then `us-east1`.
  Tune the machine-type list in `lib/300.exports.sh` and
  `cloud-run/factorio-starter/app/config.py` (keep them in sync).
- **Saves are region-safe:** VM startup loads the globally newest autosave from
  any location's saves bucket; shutdown/cron writes to the co-located bucket — so
  the save follows the server across regions.
- **DNS:** `roll-vm.sh` updates the Cloud DNS A record. The web starter still does
  not (DNS update is commented out, unchanged); `/status` reports the IP.

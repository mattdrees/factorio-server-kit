#!/usr/bin/env bash
set -euo pipefail

FACTORIO_ROOT="$(cd "$(dirname "${BASH_SOURCE[-1]}")" && git rev-parse --show-toplevel)"
readonly FACTORIO_ROOT

# Source project configuration
for lib in "$FACTORIO_ROOT"/lib/*.sh; do
  # shellcheck disable=SC1090
  source "$lib"
done

cd "$FACTORIO_ROOT/cloud-run/factorio-starter"

echo "Building container image..."
gcloud builds submit \
  --tag "gcr.io/${CLOUDSDK_CORE_PROJECT:?}/factorio-starter:latest" \
  .

echo ""
echo "Deploying infrastructure via Terraform..."
cd "$FACTORIO_ROOT/terraform"
./plan.sh
./apply.sh

echo ""
echo "Deployment complete!"
echo ""
echo "Service URL:"
SERVICE_URL=$(gcloud run services describe factorio-starter \
  --region="${CLOUDSDK_COMPUTE_REGION:?}" \
  --format="value(status.url)")

echo "$SERVICE_URL"
echo ""
echo "Open the web UI in your browser:"
echo "  open $SERVICE_URL"
echo ""
echo "Or test with curl:"
echo "  curl -X POST $SERVICE_URL/start -H 'Authorization: Bearer Tanager'"
echo "  curl -X GET $SERVICE_URL/status -H 'Authorization: Bearer Tanager'"

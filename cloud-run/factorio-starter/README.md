# Factorio Server Starter

Cloud Run service that allows players to start Factorio servers via a simple web UI or API.

## Features

- **Web UI**: Clean, modern interface at the root URL
- **REST API**: Simple endpoints for programmatic access
- **Async Operations**: Server creation happens in background
- **Single Server**: Only one server allowed at a time (cost protection)
- **Authentication**: Hardcoded API key "Tanager" (MVP simplicity)

## Quick Start

### Prerequisites

- Google Cloud SDK (`gcloud`) installed and authenticated
- `CLOUDSDK_CORE_PROJECT` environment variable set
- Required APIs enabled (done via Terraform)
- Factorio VM template built (packtorio-*)

### Deploy

```bash
./deploy.sh
```

This will:
1. Build the Docker image
2. Deploy infrastructure via Terraform
3. Output the service URL

### Use the Web UI

Simply open the service URL in your browser:

```bash
open https://factorio-starter-xxxxx.run.app
```

## API Usage

### Start Server

```bash
curl -X POST https://factorio-starter-xxxxx.run.app/start \
  -H "Authorization: Bearer Tanager"
```

Returns `202 Accepted` immediately:
```json
{
  "status": "creating",
  "message": "Server creation started",
  "started_at": "2025-11-28T12:00:00Z"
}
```

### Check Status

```bash
curl -X GET https://factorio-starter-xxxxx.run.app/status \
  -H "Authorization: Bearer Tanager"
```

Returns current status:
- `none`: No server
- `creating`: Being created (check back in ~1-2 minutes)
- `running`: Server is ready (includes IP and connection details)
- `error`: Creation failed (includes error message)

### Health Check

```bash
curl https://factorio-starter-xxxxx.run.app/health
```

## Local Development

### Setup

```bash
# Set environment
export GOOGLE_CLOUD_PROJECT=your-project-id

# Authenticate with GCP
gcloud auth application-default login

# Install dependencies
pip install -r requirements.txt
```

### Run Locally

```bash
# Start development server
uvicorn main:app --reload --port 8080

# Test
curl -X POST http://localhost:8080/start -H "Authorization: Bearer Tanager"
curl -X GET http://localhost:8080/status -H "Authorization: Bearer Tanager"
```

### Run Tests

```bash
pytest tests/ -v
```

## Architecture

```
Player → Web UI / API → Cloud Run Service
                           ↓
                  FastAPI (async)
                           ↓
            ┌──────────────┴──────────────┐
            ↓                             ↓
    Google Compute Engine          Cloud DNS
    (create VM from template)   (update A record)
```

**Key Components**:
- `main.py`: FastAPI app entry point
- `app/api.py`: Route handlers (/start, /status, /health)
- `app/compute.py`: GCE operations (create VM, cleanup)
- `app/dns.py`: DNS updates (atomic transactions)
- `app/state.py`: In-memory state (single server)
- `app/auth.py`: API key validation
- `static/index.html`: Web UI

## Configuration

Environment variables (set in Terraform):
- `GOOGLE_CLOUD_PROJECT`: GCP project ID (auto-provided by Cloud Run)
- `FACTORIO_IMAGE_FAMILY`: "packtorio" (instance template name pattern)
- `FACTORIO_DNS_ZONE`: "factorio-server" (Cloud DNS zone name)
- `FACTORIO_DNS_NAME`: "factorio.menagerie.games" (DNS record to update)

## Security

- **API Key**: Hardcoded to "Tanager" in `app/auth.py` for MVP simplicity
- **Public Endpoint**: Anyone can access the web UI, but API calls require the key
- **Cost Protection**: Only one server allowed at a time
- **Auto-Shutdown**: Existing goppuku service shuts down idle servers

## Troubleshooting

### "No packtorio-* templates found"

Build the VM template first:
```bash
cd cloud-build/1-factorio-server
./build.sh
```

### "Permission denied" errors

Ensure the service account has required permissions:
- `roles/compute.instanceAdmin.v1`
- `roles/dns.admin`
- `roles/storage.objectViewer`
- `roles/logging.logWriter`

### Server stuck in "creating" state

Check Cloud Run logs:
```bash
gcloud run services logs read factorio-starter \
  --region=us-central1 \
  --limit=50
```

## Future Enhancements

- Secret Manager for API key
- Multiple API keys with per-player permissions
- Rate limiting (prevent spam)
- Location selection in Web UI
- Auto-refresh status
- WebSocket for real-time updates

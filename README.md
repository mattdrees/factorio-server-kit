# Factorio Server Kit 👋

[![License: The Unlicense](https://img.shields.io/badge/License-The%20Unlicense-yellow.svg)][unlicense]

> Run your own [Factorio] server on Google Cloud, cheaply and (mostly) automatically.

Factorio Server Kit stands up a Factorio game server on Google Cloud Platform. It keeps running costs
low with an auto-shutdown service that stops the server when it's empty, and gives you two ways to
launch a server:

- **From your machine** — the `roll-vm.sh` Bash script (full control, all the knobs).
- **From a browser** — a [Cloud Run "starter" service](cloud-run/factorio-starter/) with a small web
  UI and REST API, so players can bring the server up themselves without a local toolchain.

Infrastructure is managed with [Terraform], VM images are baked with [Packer] via Cloud Build, and a
Go [Cloud Function] periodically cleans up terminated instances.

## How it works

```
                          ┌─────────────────────────────────────────────┐
  Player (browser) ─────▶ │  Cloud Run: factorio-starter (FastAPI)       │
                          │  POST /start ─enqueue▶ Cloud Tasks ─OIDC▶     │
                          │  /internal/create ─▶ create VM from template  │
                          └───────────────────────┬─────────────────────-┘
                                                   │
  You (CLI) ── roll-vm.sh ──────────────────────▶  │
                                                   ▼
                                     ┌──────────────────────────────┐
                                     │  Compute Engine VM            │
                                     │  from newest `packtorio-*`    │
                                     │  instance template:           │
                                     │   • Factorio server container │
                                     │   • goppuku (auto-shutdown)   │
                                     │   • Graftorio (optional)      │
                                     └──────────────┬───────────────-┘
                                                    │ updates
                                                    ▼
                                          Cloud DNS A record
                                       (factorio.menagerie.games)

  Cloud Scheduler ─▶ Pub/Sub ─▶ Cloud Function (Go): delete terminated VMs & orphaned disks
```

Both launch paths create a VM from the most recent `packtorio-*` instance template. If the chosen
zone is out of capacity, they **walk the fallback list**: they exhaust every zone in the target region
with the template's default machine type, then downgrade through alternate machine types across those
same zones, before moving on to the next region. Saves are stored per-region but a starting server
loads the globally newest autosave, so the save follows the server wherever it lands.

## Key components

| Area | Path | What it does |
| --- | --- | --- |
| Bash scripts | [`scripts/`](scripts/) | Roll up, delete, and manage servers from your machine. |
| Shared library | [`lib/`](lib/) | Sourced by every script (numeric order): prereq checks, location/zone parsing, DNS updates, fallback logic, exports. |
| Locations | [`lib/locations.json`](lib/locations.json) | Valid regions and their zones; one is marked `"default": true`. |
| Web starter | [`cloud-run/factorio-starter/`](cloud-run/factorio-starter/) | Cloud Run FastAPI service + web UI/API to start a server. |
| VM image build | [`cloud-build/`](cloud-build/) | Two-stage Cloud Build: a Packer Docker image, then the Factorio VM image. |
| Cleanup function | [`functions/`](functions/) | Go Cloud Function that deletes terminated VMs and orphaned disks. |
| Infrastructure | [`terraform/`](terraform/) | Pub/Sub, Scheduler, Cloud Run, Cloud Tasks, Secret Manager, buckets, firewall, service accounts. |
| Config | [`config/`](config/), [`mods/`](mods/) | Server, map, mod, admin, and whitelist settings. |

## Prerequisites

Install these, put them on your `$PATH`, and (where noted) authenticate:

- [Google Cloud SDK] (`gcloud`) — [install][gc-inst] and [authorise][gc-auth]
- [jq]
- [Terraform]

For hacking on the Bash scripts, the linter (`./lint-bash.sh`, run on pre-push via [lefthook]) also
wants `shfmt`, `shellharden`, and `shellcheck`.

You'll also need a Google Cloud project on the [GCP Free Tier] (or otherwise). **You are responsible
for the costs this project incurs.** Everything here is tuned to minimise spend, but that's on you to
monitor.

## Setup

```bash
# 1. Point at your GCP project.
export CLOUDSDK_CORE_PROJECT=my-factorio-server-kit

# 2. Provision infrastructure. init.sh creates the remote-state bucket
#    (gs://<project>-tfstate) and runs `terraform init`.
cd terraform
./init.sh
./plan.sh
./apply.sh
cd ..

# 3. Build the VM image (two stages). Do the Packer builder first.
cd cloud-build/0-packer     # see this dir's README
./build.sh
cd ../1-factorio-server
./build.sh                  # add --graftorio to bake in Grafana + Prometheus monitoring
cd ../..

# 4. (Optional) Deploy the web starter so players can launch from a browser.
cd cloud-run/factorio-starter
./deploy.sh                 # builds the container, then applies Terraform, and prints the URL
cd ../..
```

Terraform provisions, among other things, the Cloud DNS record the servers point at
(`factorio.menagerie.games` by default — change `FACTORIO_DNS_NAME` in
[`lib/300.exports.sh`](lib/300.exports.sh) and the starter's Terraform env to your own domain), the
`<project>-saves-<location>` buckets, and the Secret Manager secret (`factorio-starter-api-key`) that
holds the web starter's API key.

## Usage

### From the command line

```bash
cd scripts

./roll-vm.sh                          # deploy to the default location
./roll-vm.sh --sydney                 # deploy to a specific location (see --help for the list)
./roll-vm.sh --machine-type=e2-medium # pin a machine type
./roll-vm.sh --logs                   # open Cloud Logging after creation
./roll-vm.sh --help                   # full option list, including all locations

./delete-vm.sh                        # delete all running servers
./delete-vm.sh 'factorio-*'           # delete servers matching a name pattern
```

`roll-vm.sh` picks the newest `packtorio-*` instance template, creates a VM from it (walking
zones and machine types on capacity stockouts), and updates the Cloud DNS A record to the new IP.

Other handy scripts in [`scripts/`](scripts/):

- `let-me-in.sh` — open the firewall to your current public IP.
- `snapshot-saves.sh` — archive every `-saves-<location>` bucket into a timestamped Archive-class bucket.
- `throwaway-vm.sh` — spin up a scratch VM for poking around.
- `last-baked.sh` — show the most recently built image/template.
- `settings.sync.factorio.sh` / `settings.diff.factorio.sh` — push/compare local config against a running server.
- `grafana-setup.sh`, `check-signed.sh` (DNSSEC), `gsutil-sync.sh`, `list-all-project-resources.sh` — one-off utilities.

### From a browser (Cloud Run starter)

Once deployed, open the service URL for the web UI, or drive the API directly. The API requires the
key stored in Secret Manager; the web UI is public but can only trigger authenticated actions.

```bash
STARTER_URL=https://factorio-starter-xxxxx.run.app

# Start a server (returns 202 immediately; creation runs in the background via Cloud Tasks).
curl -X POST "$STARTER_URL/start" -H "Authorization: Bearer <your-api-key>"

# Poll status: none | creating | running | error.
curl -X GET "$STARTER_URL/status" -H "Authorization: Bearer <your-api-key>"
```

Only one server is allowed at a time (cost protection). See the
[starter's README](cloud-run/factorio-starter/README.md) for the full API, local-dev instructions,
and architecture notes.

## Configuration files

Server behaviour is driven by the JSON under [`config/`](config/) and [`mods/`](mods/):

- `config/server-settings.json` — server configuration
- `config/map-settings.json`, `config/map-gen-settings.json` — gameplay and map generation (can be
  [generated in-game from a map exchange string][map-settings])
- `config/server-adminlist.json`, `config/server-whitelist.json` — admins and whitelist
- `mods/mod-list.json` — enabled mods

## Cost optimisation

- **[goppuku]** shuts the server down after 15 consecutive minutes with zero players — the main lever,
  since you only pay for compute while people are actually playing.
- The Cloud Run starter runs with **request-based (CPU-throttled) billing** and defers slow work to
  Cloud Tasks, so you pay for CPU only while a request is in flight.
- The **cleanup Cloud Function** (triggered periodically by Cloud Scheduler → Pub/Sub) removes
  terminated instances and orphaned disks so they don't accrue storage charges.

## Related projects

- **[goppuku]** — a small Go service that shuts a server down when it's been empty for fifteen
  minutes; installed into the VM image by the [Packer provisioner](cloud-build/1-factorio-server/provisioner.sh).
- **[Graftorio]** — optional Grafana + Prometheus monitoring, baked in with `build.sh --graftorio`.

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you'd like to
change. Please keep documentation up to date, and run `./lint-bash.sh` before pushing.

## Credit

This project began as a fork of [jlucktay/factorio-server-kit][jlucktay-repo] by James Lucktaylor, and
has since grown a Cloud Run starter service, Cloud Tasks–backed provisioning, zone/machine-type
fallback, and more. Thanks to the original author for the foundation.

## License

Released into the public domain under [the Unlicense].

[Cloud Function]: https://cloud.google.com/functions
[Factorio]: https://factorio.com
[GCP Free Tier]: https://cloud.google.com/free/
[Google Cloud SDK]: https://cloud.google.com/sdk
[Graftorio]: https://github.com/afex/graftorio
[Packer]: https://www.packer.io
[Terraform]: https://www.terraform.io
[gc-auth]: https://cloud.google.com/sdk/docs/authorizing
[gc-inst]: https://cloud.google.com/sdk/install
[goppuku]: https://github.com/jlucktay/goppuku
[jlucktay-repo]: https://github.com/jlucktay/factorio-server-kit
[jq]: https://jqlang.github.io/jq/
[lefthook]: https://github.com/evilmartians/lefthook
[map-settings]: https://wiki.factorio.com/Command_line_parameters#Creating_the_JSON_files_from_a_map_exchange_string
[the Unlicense]: https://unlicense.org
[unlicense]: https://choosealicense.com/licenses/unlicense/

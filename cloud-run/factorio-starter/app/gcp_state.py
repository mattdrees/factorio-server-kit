"""Derive server state from GCP resources (stateless)."""
from google.cloud import compute_v1
from datetime import datetime
from typing import Optional, Dict, Any
import logging
from app.config import settings
from app.rcon import check_rcon_ready

logger = logging.getLogger(__name__)


def get_server_status() -> Dict[str, Any]:
    """
    Derive server status by querying GCP resources.
    This is stateless - always queries GCP for current state.

    Returns:
        Dictionary with status and relevant details
    """
    try:
        compute = compute_v1.InstancesClient()

        # Get all zones from locations (we'll check all of them)
        # For now, check the default zone (us-central1-c)
        zones = ["us-central1-c"]  # TODO: Load from locations.json if needed

        instances = []
        for zone in zones:
            try:
                request = compute_v1.ListInstancesRequest(
                    project=settings.google_cloud_project,
                    zone=zone,
                    filter="name:factorio-*"
                )
                zone_instances = list(compute.list(request=request))
                instances.extend([(zone, inst) for inst in zone_instances])
            except Exception as e:
                logger.debug(f"Error listing instances in zone {zone}: {e}")
                continue

        if not instances:
            return {
                "status": "none",
                "message": "No server currently running or being created"
            }

        # Sort by creation timestamp (newest first)
        instances.sort(key=lambda x: x[1].creation_timestamp, reverse=True)
        zone, instance = instances[0]

        # Derive status from GCP instance status
        gcp_status = instance.status

        if gcp_status in ["PROVISIONING", "STAGING", "REPAIRING"]:
            return {
                "status": "creating",
                "message": "Server is being created",
                "instance_name": instance.name,
                "zone": zone,
                "started_at": instance.creation_timestamp
            }

        elif gcp_status == "RUNNING":
            # Instance is running, check if Factorio is ready via RCON
            instance_ip = _get_instance_ip(instance)

            if not instance_ip:
                return {
                    "status": "error",
                    "message": "Instance running but no IP address found",
                    "instance_name": instance.name
                }

            # Check RCON readiness
            if check_rcon_ready(instance_ip, port=27015, timeout=3):
                # Factorio is ready!
                return {
                    "status": "running",
                    "message": "Server is ready for players",
                    "instance_name": instance.name,
                    "instance_ip": instance_ip,
                    "dns_name": "factorio.menagerie.games",
                    "zone": zone,
                    "created_at": instance.creation_timestamp
                }
            else:
                # VM is up but Factorio not ready yet
                return {
                    "status": "starting",
                    "message": "VM is up, waiting for Factorio game server to be ready",
                    "instance_name": instance.name,
                    "instance_ip": instance_ip,
                    "zone": zone,
                    "created_at": instance.creation_timestamp
                }

        elif gcp_status in ["STOPPING", "TERMINATED", "SUSPENDED", "SUSPENDING"]:
            # Treat terminated/stopping instances as "none"
            return {
                "status": "none",
                "message": "No server currently running or being created"
            }

        else:
            # Unknown status
            return {
                "status": "error",
                "message": f"Unknown instance status: {gcp_status}",
                "instance_name": instance.name
            }

    except Exception as e:
        logger.error(f"Error deriving server status: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Failed to query server status: {str(e)}"
        }


def _get_instance_ip(instance) -> Optional[str]:
    """Extract external IP from instance."""
    try:
        if instance.network_interfaces:
            access_configs = instance.network_interfaces[0].access_configs
            if access_configs:
                return access_configs[0].nat_i_p
    except Exception as e:
        logger.error(f"Error getting instance IP: {e}")
    return None


def has_running_or_creating_instance() -> bool:
    """
    Check if there's already a server running or being created.
    Used by /start endpoint to prevent duplicate creation.
    """
    status = get_server_status()
    return status["status"] in ["creating", "starting", "running"]

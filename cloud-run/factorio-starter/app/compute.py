from google.cloud import compute_v1, storage
from datetime import datetime
import json
import logging
from app.dns import update_dns_record
from app.config import settings
from app.exceptions import CapacityError

logger = logging.getLogger(__name__)

# GCP operation error codes that mean "this zone has no capacity right now" and
# that we should retry the creation in a different zone.
CAPACITY_ERROR_CODES = {
    "ZONE_RESOURCE_POOL_EXHAUSTED",
    "ZONE_RESOURCE_POOL_EXHAUSTED_WITH_DETAILS",
    "RESOURCE_POOL_EXHAUSTED",
}


async def create_server_async():
    """
    Background task to create server.
    Note: This is now stateless - it just creates the instance.
    Status is derived by querying GCP in the /status endpoint.
    """
    try:
        # 1. Load locations from GCS.
        locations = await load_locations_json()
        default_loc = get_default_location(locations)
        location_name = default_loc["location"]
        all_zones = [zone for loc in locations for zone in loc.get("zones", [])]
        if not all_zones:
            raise Exception("No zones found in locations.json")

        compute = compute_v1.InstancesClient()

        # 2. Find latest instance template
        templates_client = compute_v1.InstanceTemplatesClient()
        request = compute_v1.ListInstanceTemplatesRequest(
            project=settings.google_cloud_project,
            filter="name:packtorio-*"
        )
        templates = list(templates_client.list(request=request))

        if not templates:
            raise Exception("No packtorio-* instance templates found")

        # Sort by creation timestamp descending (newest first)
        templates.sort(key=lambda t: t.creation_timestamp, reverse=True)
        template = templates[0]

        # 3. Generate instance name once, reused across zone attempts
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        instance_name = f"factorio-{location_name}-{timestamp}"

        # 4. Create instance from template, walking the fallback attempts on
        #    capacity shortages. "Stay in region, then downgrade": for each region
        #    (default first), exhaust its zones with the preferred machine type,
        #    then downgrade the machine type across those zones, before moving on
        #    to the next region.
        machine_types = [None] + list(settings.machine_type_fallbacks)
        attempts = build_create_attempts(locations, default_loc, machine_types)

        created_zone = None
        last_capacity_error = None
        for zone, machine_type in attempts:
            mt_label = machine_type or "template default"
            logger.info(
                f"Creating instance {instance_name} from template {template.name} "
                f"in zone {zone} (machine type: {mt_label})"
            )
            try:
                operation = create_instance(
                    compute, zone, instance_name, template.self_link, machine_type=machine_type
                )
                wait_for_operation(operation, zone)
                created_zone = zone
                logger.info(f"Instance {instance_name} created in zone {zone} with machine type {mt_label}")
                break
            except CapacityError as e:
                logger.warning(f"No capacity for {mt_label} in zone {zone}, trying next option: {e}")
                last_capacity_error = e
                continue

        if created_zone is None:
            raise Exception(
                f"All zones and machine types exhausted; no capacity to create {instance_name}. "
                f"Last error: {last_capacity_error}"
            )

        # 5. Get instance IP
        instance = compute.get(
            project=settings.google_cloud_project,
            zone=created_zone,
            instance=instance_name
        )
        instance_ip = instance.network_interfaces[0].access_configs[0].nat_i_p

        logger.info(f"Instance created successfully: {instance_name} at {instance_ip}")

        # 6. Now that the replacement is up, delete older instances across all
        #    candidate zones (create-before-delete).
        for zone in all_zones:
            for old in list_instances(compute, zone, filter="name:factorio-*"):
                if old.name != instance_name:
                    delete_instance(compute, zone, old.name)

        # Note: We don't poll RCON or update state here anymore.
        # The /status endpoint will query GCP and check RCON on-demand.

        # 7. Update DNS (commented out - not configured)
        # await update_dns_record(
        #     zone_name="factorio-server",
        #     dns_name="factorio.menagerie.games.",
        #     new_ip=instance_ip
        # )

    except Exception as e:
        logger.error(f"Failed to create server: {e}", exc_info=True)
        # No state to update - errors will be reflected in GCP instance status


def list_instances(compute: compute_v1.InstancesClient, zone: str, filter: str = None):
    """List instances matching filter"""
    request = compute_v1.ListInstancesRequest(
        project=settings.google_cloud_project,
        zone=zone,
        filter=filter
    )
    return list(compute.list(request=request))


def delete_instance(compute: compute_v1.InstancesClient, zone: str, instance_name: str):
    """Delete instance"""
    logger.info(f"Deleting instance: {instance_name}")
    operation = compute.delete(
        project=settings.google_cloud_project,
        zone=zone,
        instance=instance_name
    )
    wait_for_operation(operation, zone)


def create_instance(compute: compute_v1.InstancesClient, zone: str, instance_name: str, template_link: str,
                    machine_type: str = None):
    """Create instance from template, optionally overriding the machine type."""
    logger.info(f"Creating instance: {instance_name} from template")

    instance_resource = compute_v1.Instance(name=instance_name)
    if machine_type:
        instance_resource.machine_type = f"zones/{zone}/machineTypes/{machine_type}"

    request = compute_v1.InsertInstanceRequest(
        project=settings.google_cloud_project,
        zone=zone,
        source_instance_template=template_link,
        instance_resource=instance_resource
    )
    return compute.insert(request=request)


def wait_for_operation(operation, zone: str):
    """Wait for operation to complete"""
    zone_operations = compute_v1.ZoneOperationsClient()

    while operation.status != compute_v1.Operation.Status.DONE:
        operation = zone_operations.get(
            project=settings.google_cloud_project,
            zone=zone,
            operation=operation.name
        )

    if operation.error:
        if _is_capacity_error(operation.error):
            raise CapacityError(f"Zone {zone} lacks capacity: {operation.error}")
        raise Exception(f"Operation failed: {operation.error}")


def _is_capacity_error(operation_error) -> bool:
    """True if the operation failed because a zone ran out of capacity."""
    try:
        for err in operation_error.errors:
            if err.code in CAPACITY_ERROR_CODES:
                return True
    except Exception:
        pass
    return False


def build_create_attempts(locations: list, default_loc: dict, machine_types: list) -> list:
    """Ordered (zone, machine_type) attempts as "stay in region, then downgrade":
    for each region/location (default first), exhaust its zones with the preferred
    machine type, then downgrade the machine type across those same zones, before
    moving on to the next region. machine_types[0] is typically None (the instance
    template's default machine type)."""
    ordered_locations = [default_loc] + [loc for loc in locations if loc is not default_loc]
    attempts = []
    for loc in ordered_locations:
        zones = loc.get("zones", [])
        for machine_type in machine_types:
            for zone in zones:
                attempts.append((zone, machine_type))
    return attempts


async def load_locations_json():
    """Load locations.json from GCS"""
    storage_client = storage.Client()
    bucket = storage_client.bucket(f"{settings.google_cloud_project}-storage")
    blob = bucket.blob("lib/locations.json")
    content = blob.download_as_text()
    return json.loads(content)


def get_default_location(locations: list) -> dict:
    """Get location marked as default"""
    for loc in locations:
        if loc.get("default"):
            return loc
    raise ValueError("No default location found in locations.json")

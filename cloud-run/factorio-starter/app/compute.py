from google.cloud import compute_v1, storage
from datetime import datetime
import json
import logging
from app.dns import update_dns_record
from app.config import settings

logger = logging.getLogger(__name__)


async def create_server_async():
    """
    Background task to create server.
    Note: This is now stateless - it just creates the instance.
    Status is derived by querying GCP in the /status endpoint.
    """
    try:
        # 1. Load locations from GCS
        locations = await load_locations_json()
        default_loc = get_default_location(locations)
        zone = default_loc["zone"]
        location_name = default_loc["location"]

        compute = compute_v1.InstancesClient()

        # 2. Delete any non-RUNNING instances (cleanup)
        all_instances = list_instances(compute, zone, filter="name:factorio-*")
        for instance in all_instances:
            if instance.status != "RUNNING":
                delete_instance(compute, zone, instance.name)

        # 3. Find latest instance template
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

        # 4. Generate instance name
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        instance_name = f"factorio-{location_name}-{timestamp}"

        # 5. Create instance from template
        logger.info(f"Creating instance: {instance_name} from template {template.name}")
        operation = create_instance(
            compute,
            zone,
            instance_name,
            template.self_link
        )

        # Wait for operation to complete
        wait_for_operation(operation, zone)

        # 6. Get instance IP
        instance = compute.get(
            project=settings.google_cloud_project,
            zone=zone,
            instance=instance_name
        )
        instance_ip = instance.network_interfaces[0].access_configs[0].nat_i_p

        logger.info(f"Instance created successfully: {instance_name} at {instance_ip}")

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


def create_instance(compute: compute_v1.InstancesClient, zone: str, instance_name: str, template_link: str):
    """Create instance from template"""
    logger.info(f"Creating instance: {instance_name} from template")

    request = compute_v1.InsertInstanceRequest(
        project=settings.google_cloud_project,
        zone=zone,
        source_instance_template=template_link,
        instance_resource=compute_v1.Instance(
            name=instance_name
        )
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
        raise Exception(f"Operation failed: {operation.error}")


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

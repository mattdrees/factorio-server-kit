from google.cloud import dns
import logging
from app.config import settings

logger = logging.getLogger(__name__)


async def update_dns_record(zone_name: str, dns_name: str, new_ip: str):
    """
    Update DNS A record using atomic transaction pattern.

    Replicates lib/204.func.dns.update.sh:
    1. Start transaction
    2. Get old IP from existing record
    3. Remove old record
    4. Add new record
    5. Execute transaction
    """
    logger.info(f"Updating DNS record {dns_name} to {new_ip}")

    client = dns.Client(project=settings.google_cloud_project)
    zone = client.zone(zone_name)

    # Reload zone to get current state
    zone.reload()

    # Start transaction
    changes = zone.changes()

    # Get existing record
    existing_records = list(zone.list_resource_record_sets(
        name=dns_name,
        type_='A'
    ))

    # Remove old record if exists
    if existing_records:
        old_record = existing_records[0]
        logger.info(f"Removing old DNS record: {old_record.rrdatas}")
        changes.delete_record_set(old_record)

    # Add new record
    new_record = zone.resource_record_set(
        name=dns_name,
        record_type='A',
        ttl=30,
        rrdatas=[new_ip]
    )
    logger.info(f"Adding new DNS record: {new_ip}")
    changes.add_record_set(new_record)

    # Execute transaction
    changes.create()
    logger.info("DNS update complete")

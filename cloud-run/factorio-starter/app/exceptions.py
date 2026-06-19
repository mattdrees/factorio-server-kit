# Custom exception classes for factorio-starter


class CapacityError(Exception):
    """Raised when a zone cannot fulfill an instance creation due to a
    resource shortage (e.g. ZONE_RESOURCE_POOL_EXHAUSTED), signalling that the
    caller should retry in a different zone."""

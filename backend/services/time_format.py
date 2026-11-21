"""UTC serialization for material timestamps; business date strings stay separate."""
from datetime import timezone


def utc_timestamp(value):
    if value is None:
        return None
    # Existing DateTime columns store naive UTC; aware values are normalized.
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

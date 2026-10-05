from datetime import UTC, datetime

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers


@extend_schema_field(OpenApiTypes.INT)
class UnixTimeField(serializers.Field):
    """timestamptz in the database, integer Unix seconds on the wire (ICD §2)."""

    def to_representation(self, value: datetime) -> int:
        return int(value.timestamp())

    def to_internal_value(self, data) -> datetime:
        try:
            return datetime.fromtimestamp(int(data), tz=UTC)
        except TypeError, ValueError, OverflowError:
            raise serializers.ValidationError("must be Unix seconds (integer)") from None

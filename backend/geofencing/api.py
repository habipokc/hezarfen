"""Geofence CRUD and geofence event list (ICD §7.2)."""

import json
import logging
import time
from datetime import UTC, datetime

import redis
import shapely
from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry
from django.db import transaction
from django.db.models import OuterRef, Subquery
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import generics, serializers, viewsets
from rest_framework.pagination import CursorPagination
from rest_framework_gis.fields import GeometryField
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from hezarfen.api.fields import UnixTimeField
from hezarfen.api.params import parse_bool, parse_int, parse_unix
from tracking.models import Aircraft

from .models import Geofence, GeofenceEvent
from .validation import GeometryError, validate_polygon

log = logging.getLogger(__name__)


class GeofenceSerializer(GeoFeatureModelSerializer):
    # output only: 6 decimals = ~0.1 m; buffers computed in PostGIS carry 15
    geom = GeometryField(precision=6)
    created_at = UnixTimeField(read_only=True)

    class Meta:
        model = Geofence
        geo_field = "geom"
        id_field = False
        fields = ("geom", "id", "name", "kind", "active", "created_at")
        read_only_fields = ("id", "kind")

    def validate_geom(self, value: GEOSGeometry) -> GEOSGeometry:
        if value.srid not in (None, 4326):
            value.transform(4326)
        try:
            poly = validate_polygon(shapely.from_wkb(bytes(value.wkb)), settings.REGION_BBOX)
        except GeometryError as exc:
            raise serializers.ValidationError(str(exc), code="invalid_geometry") from None
        return GEOSGeometry(memoryview(poly.wkb), srid=4326)  # bytes would be read as text


def publish_geofences_changed(geofence_id: int, action: str) -> None:
    """Tell the relay to reload its geofence cache (ICD §4.3). Best effort: the change is
    already committed, so a Redis outage must not turn a successful request into an error."""
    message = {
        "schema": "geofences.changed/v1",
        "ts": int(time.time()),
        "geofence_id": geofence_id,
        "action": action,
    }
    try:
        client = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=2)
        client.publish(settings.GEOFENCES_CHANGED_CHANNEL, json.dumps(message))
    except redis.RedisError as exc:
        log.warning("geofences.changed publish failed: %s", exc)


def publish_on_commit(geofence_id: int, action: str) -> None:
    # after COMMIT, so the relay never reloads before the change is visible to it
    transaction.on_commit(lambda: publish_geofences_changed(geofence_id, action))


@extend_schema_view(
    list=extend_schema(
        parameters=[OpenApiParameter("active", bool, description="filter by active flag")]
    )
)
class GeofenceViewSet(viewsets.ModelViewSet):
    serializer_class = GeofenceSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        qs = Geofence.objects.all()
        if self.action == "list" and "active" in self.request.query_params:
            qs = qs.filter(active=parse_bool(self.request.query_params["active"], "active"))
        return qs

    def perform_create(self, serializer):
        fence = serializer.save(kind=Geofence.Kind.USER_DRAWN)
        publish_on_commit(fence.id, "created")

    def perform_update(self, serializer):
        fence = serializer.save()
        publish_on_commit(fence.id, "updated")

    def perform_destroy(self, instance):
        fence_id = instance.id
        instance.delete()
        publish_on_commit(fence_id, "deleted")


class GeofenceRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Geofence
        fields = ("id", "name")


class GeofenceEventSerializer(serializers.ModelSerializer):
    """ICD §6.3 GeofenceEvent without the WebSocket `type` discriminator."""

    geofence = GeofenceRefSerializer()
    callsign = serializers.CharField(allow_null=True)
    ts = UnixTimeField()
    lon = serializers.FloatField(source="geom.x")
    lat = serializers.FloatField(source="geom.y")

    class Meta:
        model = GeofenceEvent
        fields = ("id", "geofence", "icao24", "callsign", "event", "ts", "lon", "lat")


class EventCursorPagination(CursorPagination):
    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 500
    ordering = ("-ts", "-id")  # unique and stable, as cursor pagination needs


@extend_schema(
    parameters=[
        OpenApiParameter("since", int, description="only events at or after this Unix time"),
        OpenApiParameter("geofence", int, description="only events of this geofence id"),
    ]
)
class GeofenceEventList(generics.ListAPIView):
    serializer_class = GeofenceEventSerializer
    pagination_class = EventCursorPagination

    def get_queryset(self):
        q = self.request.query_params
        qs = GeofenceEvent.objects.select_related("geofence").annotate(
            # geofence_events.icao24 is not a FK (history outlives identities)
            callsign=Subquery(
                Aircraft.objects.filter(icao24=OuterRef("icao24")).values("callsign")[:1]
            )
        )
        if "since" in q:
            qs = qs.filter(ts__gte=datetime.fromtimestamp(parse_unix(q["since"], "since"), tz=UTC))
        if "geofence" in q:
            qs = qs.filter(geofence_id=parse_int(q["geofence"], "geofence", minimum=1))
        return qs

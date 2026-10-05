"""Aircraft REST endpoints (ICD §7.2): live map, detail, track, playback, stats."""

import json
import logging
import time
import urllib.request
from datetime import UTC, datetime, timedelta

from django.conf import settings
from django.contrib.gis.db.models.functions import Distance, GeometryDistance
from django.contrib.gis.geos import Point, Polygon
from django.db import connection
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from geofencing.models import GeofenceEvent
from hezarfen.api.errors import ApiError
from hezarfen.api.fields import UnixTimeField
from hezarfen.api.params import parse_bbox, parse_int, parse_unix
from reference.models import Airport, province_at

from .models import Aircraft, AircraftLatest

log = logging.getLogger(__name__)

TRACK_DEFAULT_SECONDS = 30 * 60
TRACK_MAX_SECONDS = 24 * 3600
PLAYBACK_MAX_SECONDS = 2 * 3600
PLAYBACK_DEFAULT_SECONDS = 15 * 60
# KNN by planar degree distance, then re-rank this many candidates by metric distance:
# at 41°N a degree of longitude is ~25% shorter than one of latitude, so the planar
# nearest is not always the truly nearest.
NEAREST_CANDIDATES = 8


def live_cutoff() -> datetime:
    return timezone.now() - timedelta(seconds=settings.LIVE_WINDOW_SECONDS)


# ---------------------------------------------------------------- serializers


class AircraftFeatureSerializer(GeoFeatureModelSerializer):
    """GeoJSON Feature whose properties are exactly the ICD `Aircraft` object (§6.2)."""

    icao24 = serializers.CharField(source="aircraft_id")
    callsign = serializers.CharField(source="aircraft.callsign", allow_null=True)
    lon = serializers.FloatField(source="geom.x")
    lat = serializers.FloatField(source="geom.y")
    baro_alt = serializers.FloatField(source="baro_altitude", allow_null=True)
    geo_alt = serializers.FloatField(source="geo_altitude", allow_null=True)
    vrate = serializers.FloatField(source="vertical_rate", allow_null=True)
    category = serializers.IntegerField(source="aircraft.category", allow_null=True)
    ts = UnixTimeField()

    class Meta:
        model = AircraftLatest
        geo_field = "geom"
        id_field = False
        fields = (
            "geom", "icao24", "callsign", "lon", "lat", "baro_alt", "geo_alt",
            "velocity", "heading", "vrate", "on_ground", "squawk", "category", "ts",
        )  # fmt: skip


class NearestAirportSerializer(serializers.Serializer):
    ident = serializers.CharField()
    name = serializers.CharField()
    distance_m = serializers.FloatField()


class AircraftDetailSerializer(AircraftFeatureSerializer):
    origin_country = serializers.CharField(source="aircraft.origin_country", allow_null=True)
    source = serializers.CharField()
    province = serializers.CharField(source="province_name", allow_null=True)
    nearest_airport = NearestAirportSerializer(allow_null=True)

    class Meta(AircraftFeatureSerializer.Meta):
        fields = AircraftFeatureSerializer.Meta.fields + (
            "origin_country", "source", "province", "nearest_airport",
        )  # fmt: skip


# ---------------------------------------------------------------- views


class AircraftLiveView(APIView):
    @extend_schema(
        summary="Aircraft seen in the last 60 s inside a bbox",
        parameters=[
            OpenApiParameter(
                "bbox", str, description="minLon,minLat,maxLon,maxLat (default: region bbox)"
            )
        ],
        responses=AircraftFeatureSerializer(many=True),
    )
    def get(self, request):
        raw = request.query_params.get("bbox")
        bbox = parse_bbox(raw) if raw is not None else settings.REGION_BBOX
        qs = (
            AircraftLatest.objects.select_related("aircraft")
            # `&&` (bounding-box overlap) is answered from the GiST index alone;
            # for points it is the same as "inside the bbox, edges included"
            .filter(ts__gte=live_cutoff(), geom__bboverlaps=Polygon.from_bbox(bbox))
            .order_by("aircraft_id")
        )
        return Response(AircraftFeatureSerializer(qs, many=True).data)


def nearest_airport(point: Point) -> dict | None:
    candidates = (
        Airport.objects.order_by(GeometryDistance("geom", point))  # ORDER BY geom <-> point
        .annotate(distance=Distance("geom", point))  # metres (spheroid) on 4326 geometry
        .only("ident", "name")[:NEAREST_CANDIDATES]
    )
    best = min(candidates, key=lambda a: a.distance.m, default=None)
    if best is None:
        return None
    return {"ident": best.ident, "name": best.name, "distance_m": round(best.distance.m, 1)}


class AircraftDetailView(APIView):
    @extend_schema(
        summary="Latest state of one aircraft, its province and nearest airport",
        responses=AircraftDetailSerializer,
    )
    def get(self, request, icao24: str):
        latest = get_object_or_404(
            AircraftLatest.objects.select_related("aircraft"), aircraft_id=icao24.lower()
        )
        province = province_at(latest.geom.x, latest.geom.y)
        latest.province_name = province.name if province else None
        latest.nearest_airport = nearest_airport(latest.geom)
        return Response(AircraftDetailSerializer(latest).data)


TRACK_SQL = """
SELECT ST_AsGeoJSON(ST_MakeLine(geom ORDER BY ts), 6),
       extract(epoch FROM min(ts))::bigint,
       extract(epoch FROM max(ts))::bigint,
       count(*)
FROM positions
WHERE icao24 = %s AND ts >= to_timestamp(%s)
"""


class AircraftTrackView(APIView):
    @extend_schema(
        summary="Track of one aircraft as a time-ordered LineString",
        parameters=[
            OpenApiParameter(
                "since", int, description="Unix seconds (default now - 30 min, max 24 h back)"
            )
        ],
        responses=OpenApiTypes.OBJECT,
    )
    def get(self, request, icao24: str):
        icao24 = icao24.lower()
        aircraft = get_object_or_404(Aircraft, icao24=icao24)
        now = int(time.time())
        raw = request.query_params.get("since")
        since = parse_unix(raw, "since") if raw is not None else now - TRACK_DEFAULT_SECONDS
        if since < now - TRACK_MAX_SECONDS:
            raise ApiError(
                "window_too_large", "since must be within the last 24 hours", {"since": since}
            )
        with connection.cursor() as cur:
            cur.execute(TRACK_SQL, [icao24, since])
            line, start_ts, end_ts, points = cur.fetchone()
        return Response(
            {
                "type": "Feature",
                # RFC 7946: a LineString needs at least two positions
                "geometry": json.loads(line) if points >= 2 else None,
                "properties": {
                    "icao24": icao24,
                    "callsign": aircraft.callsign,
                    "start_ts": start_ts,
                    "end_ts": end_ts,
                    "points": points,
                },
            }
        )


# Latest fix per aircraft in every bucket: DISTINCT ON keeps the first row of each
# (bucket, icao24) group, and the ORDER BY makes that the newest one.
PLAYBACK_SQL = """
SELECT DISTINCT ON (bucket, p.icao24)
       (floor(extract(epoch FROM p.ts) / %(bucket)s) * %(bucket)s)::bigint AS bucket,
       p.icao24, a.callsign, ST_X(p.geom), ST_Y(p.geom),
       p.baro_altitude, p.geo_altitude, p.velocity, p.heading, p.vertical_rate,
       p.on_ground, p.squawk, a.category, extract(epoch FROM p.ts)::bigint
FROM positions p
LEFT JOIN aircraft a ON a.icao24 = p.icao24
WHERE p.ts >= to_timestamp(%(start)s) AND p.ts < to_timestamp(%(end)s)
ORDER BY bucket, p.icao24, p.ts DESC
"""

AIRCRAFT_KEYS = (
    "icao24", "callsign", "lon", "lat", "baro_alt", "geo_alt",
    "velocity", "heading", "vrate", "on_ground", "squawk", "category", "ts",
)  # fmt: skip


class PlaybackView(APIView):
    @extend_schema(
        summary="Historical positions grouped into time buckets (window <= 2 h)",
        parameters=[
            OpenApiParameter("start", int, description="Unix seconds (default end - 15 min)"),
            OpenApiParameter("end", int, description="Unix seconds, exclusive (default now)"),
            OpenApiParameter("bucket", int, description="seconds per frame, 1-600 (default 10)"),
        ],
        responses=OpenApiTypes.OBJECT,
    )
    def get(self, request):
        q = request.query_params
        end = parse_unix(q["end"], "end") if "end" in q else int(time.time())
        start = parse_unix(q["start"], "start") if "start" in q else end - PLAYBACK_DEFAULT_SECONDS
        bucket = parse_int(q.get("bucket", "10"), "bucket", minimum=1, maximum=600)
        if start >= end:
            raise ApiError("invalid_parameter", "start must be before end", {"parameter": "start"})
        if end - start > PLAYBACK_MAX_SECONDS:
            raise ApiError(
                "window_too_large",
                "playback window must be at most 2 hours",
                {"seconds": end - start, "max_seconds": PLAYBACK_MAX_SECONDS},
            )
        frames: list[dict] = []
        with connection.cursor() as cur:
            cur.execute(PLAYBACK_SQL, {"start": start, "end": end, "bucket": bucket})
            for row in cur.fetchall():
                if not frames or frames[-1]["ts"] != row[0]:
                    frames.append({"ts": row[0], "aircraft": []})
                frames[-1]["aircraft"].append(dict(zip(AIRCRAFT_KEYS, row[1:], strict=True)))
        return Response({"start": start, "end": end, "bucket": bucket, "frames": frames})


def fetch_ingest_metrics() -> dict | None:
    try:
        with urllib.request.urlopen(settings.INGEST_METRICS_URL, timeout=1) as resp:
            return json.load(resp)
    except (OSError, ValueError) as exc:
        log.warning("ingest metrics unavailable: %s", exc)
        return None


def ingest_status(metrics: dict | None) -> str:
    if metrics is None:
        return "unreachable"
    last = metrics.get("last_poll_at")
    if not last:
        return "starting"
    age = datetime.now(UTC) - datetime.fromisoformat(last)
    return "ok" if age.total_seconds() <= settings.LIVE_WINDOW_SECONDS else "stale"


class StatsView(APIView):
    @extend_schema(
        summary="Active aircraft, recent geofence events and ingest status",
        responses=inline_serializer(
            "Stats",
            {
                "active_aircraft": serializers.IntegerField(),
                "events_last_hour": serializers.IntegerField(),
                "ingest": inline_serializer(
                    "IngestStatus",
                    {
                        "status": serializers.ChoiceField(
                            ["ok", "stale", "starting", "unreachable"]
                        ),
                        "metrics": serializers.DictField(allow_null=True),
                    },
                ),
            },
        ),
    )
    def get(self, request):
        metrics = fetch_ingest_metrics()
        return Response(
            {
                "active_aircraft": AircraftLatest.objects.filter(ts__gte=live_cutoff()).count(),
                "events_last_hour": GeofenceEvent.objects.filter(
                    ts__gte=timezone.now() - timedelta(hours=1)
                ).count(),
                "ingest": {"status": ingest_status(metrics), "metrics": metrics},
            }
        )

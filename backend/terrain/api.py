import math

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from hezarfen.api.errors import ApiError

from . import dem


def _coordinate(request, name: str, limit: float) -> float:
    raw = request.query_params.get(name)
    if raw is None:
        raise ApiError("invalid_parameter", f"{name} is required", {"parameter": name})
    try:
        value = float(raw)
    except ValueError:
        value = math.nan
    if not math.isfinite(value) or abs(value) > limit:
        raise ApiError(
            "invalid_parameter",
            f"{name} must be a number between -{limit:g} and {limit:g}",
            {"parameter": name},
        )
    return value


class ElevationView(APIView):
    @extend_schema(
        summary="Terrain elevation (Copernicus GLO-90, metres above the EGM2008 geoid)",
        parameters=[
            OpenApiParameter("lon", OpenApiTypes.DOUBLE, required=True),
            OpenApiParameter("lat", OpenApiTypes.DOUBLE, required=True),
        ],
        responses=inline_serializer(
            "Elevation",
            {
                "lon": serializers.FloatField(),
                "lat": serializers.FloatField(),
                "elevation_m": serializers.FloatField(allow_null=True),
            },
        ),
    )
    def get(self, request):
        lon = _coordinate(request, "lon", 180)
        lat = _coordinate(request, "lat", 90)
        try:
            value = dem.elevation(lon, lat)
        except dem.OutsideDem:
            raise ApiError(
                "out_of_region", "point is outside the terrain model", {"lon": lon, "lat": lat}
            ) from None
        except dem.DemUnavailable:
            raise ApiError(
                "terrain_unavailable",
                "terrain model not built yet: run `make dem`",
                status_code=503,
            ) from None
        elevation_m = None if value is None else round(value, 1)
        return Response({"lon": lon, "lat": lat, "elevation_m": elevation_m})

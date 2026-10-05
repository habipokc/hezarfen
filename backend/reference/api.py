"""Reference layers (ICD §7.2): provinces with simplified outlines, airports."""

from django.contrib.gis.db.models import GeometryField
from django.db.models import F, Func, Value
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_field
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_gis.fields import GeometryField as GeoJSONField
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from hezarfen.api.errors import ApiError
from hezarfen.api.params import parse_csv_choices

from .models import Airport, Province

# Degrees. 0.01° is ~1.1 km north-south, about one pixel at the zoom that shows the whole
# region. Natural Earth 10m outlines are already generalised (9856 vertices for 81
# provinces); 0.01 keeps 4407 of them. Raw shoreline data would shrink far more.
DEFAULT_SIMPLIFY = 0.01
MAX_SIMPLIFY = 0.1
AIRPORT_TYPES = {"large_airport", "medium_airport", "small_airport"}


@extend_schema_field(OpenApiTypes.OBJECT)  # an annotation, so the schema can't introspect it
class SimplifiedGeometryField(GeoJSONField):
    pass


class ProvinceSerializer(GeoFeatureModelSerializer):
    # 5 decimals = ~1 m; more digits only add bytes once the outline is simplified
    geom = SimplifiedGeometryField(source="outline", read_only=True, precision=5)

    class Meta:
        model = Province
        geo_field = "geom"
        id_field = False
        fields = ("geom", "id", "name", "iso_code")


class ProvinceList(APIView):
    @extend_schema(
        summary="Province boundaries, simplified with ST_Simplify",
        parameters=[
            OpenApiParameter(
                "simplify",
                float,
                description=f"tolerance in degrees, 0-{MAX_SIMPLIFY} "
                f"(default {DEFAULT_SIMPLIFY}; 0 = original geometry)",
            )
        ],
        responses=ProvinceSerializer(many=True),
    )
    def get(self, request):
        raw = request.query_params.get("simplify")
        try:
            tolerance = float(raw) if raw is not None else DEFAULT_SIMPLIFY
        except ValueError:
            tolerance = -1
        if not 0 <= tolerance <= MAX_SIMPLIFY:
            raise ApiError(
                "invalid_parameter",
                f"simplify must be a number between 0 and {MAX_SIMPLIFY}",
                {"parameter": "simplify"},
            )
        qs = Province.objects.annotate(
            outline=Func(
                F("geom"),
                Value(tolerance),
                # preserveCollapsed: keep tiny islands as a dot instead of dropping them
                Value(True),
                function="ST_Simplify",
                output_field=GeometryField(srid=4326),
            )
        ).defer("geom")
        return Response(ProvinceSerializer(qs, many=True).data)


class AirportSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = Airport
        geo_field = "geom"
        id_field = False
        fields = (
            "geom", "ident", "type", "name", "iata_code", "municipality", "elevation_m",
        )  # fmt: skip


class AirportList(APIView):
    @extend_schema(
        summary="Airports in the region",
        parameters=[
            OpenApiParameter(
                "type",
                str,
                description="comma-separated: large_airport,medium_airport,small_airport",
            )
        ],
        responses=AirportSerializer(many=True),
    )
    def get(self, request):
        qs = Airport.objects.all()
        if "type" in request.query_params:
            types = parse_csv_choices(request.query_params["type"], "type", AIRPORT_TYPES)
            qs = qs.filter(type__in=types)
        return Response(AirportSerializer(qs, many=True).data)

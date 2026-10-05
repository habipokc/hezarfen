"""Read-only views of what ingest writes. Nothing here is edited by hand."""

from django.contrib.gis import admin

from .models import Aircraft, AircraftLatest, Position


class ReadOnlyAdmin(admin.GISModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Aircraft)
class AircraftAdmin(ReadOnlyAdmin):
    list_display = ["icao24", "callsign", "origin_country", "category", "last_seen"]
    search_fields = ["icao24", "callsign"]


@admin.register(AircraftLatest)
class AircraftLatestAdmin(ReadOnlyAdmin):
    list_display = ["aircraft", "ts", "baro_altitude", "velocity", "heading", "on_ground"]
    list_select_related = ["aircraft"]
    search_fields = ["aircraft__icao24", "aircraft__callsign"]


@admin.register(Position)
class PositionAdmin(ReadOnlyAdmin):
    list_display = ["icao24", "ts", "baro_altitude", "velocity", "source"]
    search_fields = ["icao24"]
    # -id walks the primary key backwards; ordering by -ts on a BRIN-only column would sort
    # the whole table. Counting millions of rows on every page view is skipped as well.
    ordering = ["-id"]
    show_full_result_count = False

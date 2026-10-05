from django.contrib.gis import admin

from reference.admin import MARMARA_MAP

from .models import Geofence, GeofenceEvent


@admin.register(Geofence)
class GeofenceAdmin(admin.GISModelAdmin):
    gis_widget_kwargs = MARMARA_MAP
    list_display = ["name", "kind", "active", "created_at"]
    list_filter = ["kind", "active"]
    list_editable = ["active"]
    search_fields = ["name"]


@admin.register(GeofenceEvent)
class GeofenceEventAdmin(admin.ModelAdmin):
    """Events are written by the relay; the admin only shows them."""

    list_display = ["ts", "icao24", "event", "geofence"]
    list_filter = ["event", "geofence"]
    search_fields = ["icao24"]
    list_select_related = ["geofence"]  # avoids one query per row for the geofence column

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

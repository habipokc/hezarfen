from django.contrib.gis import admin

from .models import Airport, Province

# OpenLayers map centred on the Marmara region instead of Django's default (central Europe)
MARMARA_MAP = {"attrs": {"default_lon": 29.0, "default_lat": 40.9, "default_zoom": 9}}


@admin.register(Airport)
class AirportAdmin(admin.GISModelAdmin):
    gis_widget_kwargs = MARMARA_MAP
    list_display = ["ident", "name", "type", "iata_code", "municipality", "elevation_m"]
    list_filter = ["type", "iso_country"]
    search_fields = ["ident", "name", "iata_code", "municipality"]


@admin.register(Province)
class ProvinceAdmin(admin.GISModelAdmin):
    gis_widget_kwargs = {"attrs": {**MARMARA_MAP["attrs"], "default_zoom": 7}}
    list_display = ["name", "iso_code"]
    search_fields = ["name", "iso_code"]

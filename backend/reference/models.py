"""Static reference layers loaded by scripts/load_reference_data.sh (ogr2ogr)."""

from django.contrib.gis.db import models
from django.contrib.gis.geos import Point


class Airport(models.Model):
    """An OurAirports record inside the region (large/medium/small airports only)."""

    ident = models.CharField(max_length=16, unique=True)  # ICAO code when there is one
    type = models.CharField(max_length=32)  # large_airport | medium_airport | small_airport
    name = models.CharField(max_length=255)
    iata_code = models.CharField(max_length=3, null=True, blank=True)
    gps_code = models.CharField(max_length=8, null=True, blank=True)
    municipality = models.CharField(max_length=128, null=True, blank=True)
    iso_country = models.CharField(max_length=2, blank=True)
    elevation_m = models.FloatField(null=True, blank=True)  # converted from elevation_ft
    geom = models.PointField(srid=4326)

    class Meta:
        db_table = "airports"
        ordering = ["ident"]

    def __str__(self) -> str:
        return f"{self.ident} {self.name}"


class Province(models.Model):
    """A Turkish province (Natural Earth admin-1)."""

    name = models.CharField(max_length=128)
    iso_code = models.CharField(max_length=8, unique=True)  # ISO 3166-2, e.g. TR-34
    geom = models.MultiPolygonField(srid=4326)

    class Meta:
        db_table = "provinces"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


def province_at(lon: float, lat: float) -> Province | None:
    """Province whose boundary contains the point, or None (sea, or outside Türkiye)."""
    return Province.objects.filter(geom__contains=Point(lon, lat, srid=4326)).first()

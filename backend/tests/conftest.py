import pytest
from django.contrib.gis.geos import Point

from reference.models import Airport

# Real coordinates (OurAirports), lon/lat order.
LTFM = (28.7519, 41.2753)  # Istanbul Airport
LTFJ = (29.3092, 40.8986)  # Sabiha Gokcen


@pytest.fixture
def seed_airports(db):
    for ident, name, (lon, lat) in [
        ("LTFM", "Istanbul Airport", LTFM),
        ("LTFJ", "Istanbul Sabiha Gokcen International Airport", LTFJ),
    ]:
        Airport.objects.create(
            ident=ident,
            type="large_airport",
            name=name,
            iso_country="TR",
            geom=Point(lon, lat, srid=4326),
        )


@pytest.fixture
def api():
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def make_aircraft(db):
    """Create an aircraft with a latest state `age` seconds old; returns its icao24."""
    from datetime import timedelta

    from django.utils import timezone

    from tracking.models import Aircraft, AircraftLatest

    def make(icao24, lon, lat, age=0, callsign="THY1", **state):
        ts = timezone.now() - timedelta(seconds=age)
        aircraft = Aircraft.objects.create(
            icao24=icao24, callsign=callsign, origin_country="Turkey", category=4,
            first_seen=ts, last_seen=ts,
        )  # fmt: skip
        AircraftLatest.objects.create(
            aircraft=aircraft, ts=ts, geom=Point(lon, lat, srid=4326),
            source="synthetic", **state,
        )  # fmt: skip
        return icao24

    return make

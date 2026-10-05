import pytest
import pytest_asyncio
from django.contrib.gis.geos import Point

from reference.models import Airport

# Real coordinates (OurAirports), lon/lat order.
LTFM = (28.7519, 41.2753)  # Istanbul Airport
LTFJ = (29.3092, 40.8986)  # Sabiha Gokcen


@pytest.fixture(autouse=True)
def in_memory_channel_layer(settings):
    """Channels layer inside the test process; the relay and consumers meet there."""
    from channels.layers import channel_layers

    settings.CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
    channel_layers.backends.clear()
    yield
    channel_layers.backends.clear()


@pytest.fixture(autouse=True)
def test_retention_key(settings):
    """Retention runs record themselves in Redis; keep tests off the dev stack's record."""
    settings.OPS_RETENTION_KEY = "test:ops:retention:last"


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


@pytest_asyncio.fixture
async def close_async_db_connections():
    """Async tests reach the DB through sync_to_async's worker thread, whose connection
    outlives the test (CONN_MAX_AGE) and blocks dropping the test database. Close it from
    that same thread."""
    yield
    from asgiref.sync import sync_to_async
    from django.db import connections

    await sync_to_async(connections.close_all)()

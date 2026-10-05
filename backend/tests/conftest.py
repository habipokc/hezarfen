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

from django.contrib.gis.geos import GEOSGeometry
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from geofencing.models import Geofence
from reference.models import Airport

SEED_AIRPORTS = ["LTFM", "LTFJ"]  # Istanbul Airport, Sabiha Gokcen
RADIUS_M = 15_000

# Buffering a geography computes the distance in metres on the spheroid; buffering the
# same point as a 4326 geometry would treat degrees as distance and give an ellipse
# (~11 km east-west, ~15 km north-south at 41°N). quad_segs=16 -> a 64-vertex circle.
BUFFER_SQL = """
    SELECT ST_AsEWKT(ST_Buffer(geom::geography, %s, 'quad_segs=16')::geometry)
    FROM airports WHERE ident = %s
"""


class Command(BaseCommand):
    help = "Create (or refresh) 15 km geofences around LTFM and LTFJ. Safe to re-run."

    def handle(self, *args, **options):
        found = Airport.objects.filter(ident__in=SEED_AIRPORTS).values_list("ident", flat=True)
        missing = sorted(set(SEED_AIRPORTS) - set(found))
        if missing:
            raise CommandError(
                f"airports {', '.join(missing)} not found; run scripts/load_reference_data.sh "
                "(make seed) first"
            )

        for ident in SEED_AIRPORTS:
            with connection.cursor() as cur:
                cur.execute(BUFFER_SQL, [RADIUS_M, ident])
                (ewkt,) = cur.fetchone()
            fence, created = Geofence.objects.update_or_create(
                name=f"{ident} {RADIUS_M // 1000} km",
                kind=Geofence.Kind.AIRPORT_BUFFER,
                defaults={"geom": GEOSGeometry(ewkt), "active": True},
            )
            verb = "created" if created else "updated"
            self.stdout.write(f"{verb} geofence {fence.name} ({fence.geom.num_points} vertices)")

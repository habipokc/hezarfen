"""Copy reference data from ogr2ogr staging tables into the Django-owned tables.

ogr2ogr is good at reading formats and building geometry; Django owns the schema. So the
loader script lets ogr2ogr write throw-away `stage_*` tables, and this command mirrors them
into `airports` / `provinces` in one transaction, then drops the staging tables.
"""

from django.core.management.base import BaseCommand
from django.db import connection, transaction

STAGES = {
    "stage_airports": [
        """
        INSERT INTO airports (ident, type, name, iata_code, gps_code, municipality,
                              iso_country, elevation_m, geom)
        SELECT ident, type, name, NULLIF(iata_code, ''), NULLIF(gps_code, ''),
               NULLIF(municipality, ''), COALESCE(iso_country, ''),
               elevation_ft * 0.3048, ST_SetSRID(geom, 4326)
        FROM stage_airports
        WHERE ident IS NOT NULL AND geom IS NOT NULL
        ON CONFLICT (ident) DO UPDATE SET
            type = EXCLUDED.type, name = EXCLUDED.name, iata_code = EXCLUDED.iata_code,
            gps_code = EXCLUDED.gps_code, municipality = EXCLUDED.municipality,
            iso_country = EXCLUDED.iso_country, elevation_m = EXCLUDED.elevation_m,
            geom = EXCLUDED.geom
        """,
        "DELETE FROM airports WHERE ident NOT IN (SELECT ident FROM stage_airports)",
    ],
    "stage_provinces": [
        """
        INSERT INTO provinces (name, iso_code, geom)
        SELECT COALESCE(NULLIF(name_tr, ''), name), iso_3166_2,
               ST_Multi(ST_MakeValid(ST_SetSRID(geom, 4326)))
        FROM stage_provinces
        WHERE iso_3166_2 IS NOT NULL AND geom IS NOT NULL
        ON CONFLICT (iso_code) DO UPDATE SET name = EXCLUDED.name, geom = EXCLUDED.geom
        """,
        "DELETE FROM provinces WHERE iso_code NOT IN (SELECT iso_3166_2 FROM stage_provinces)",
    ],
}


class Command(BaseCommand):
    help = "Mirror stage_airports / stage_provinces (written by ogr2ogr) into the app tables."

    def handle(self, *args, **options):
        present = set(connection.introspection.table_names()) & STAGES.keys()
        if not present:
            self.stdout.write("no staging tables found; nothing to import")
            return

        with transaction.atomic(), connection.cursor() as cur:
            for stage in sorted(present):
                cur.execute(STAGES[stage][0])
                upserted = cur.rowcount
                cur.execute(STAGES[stage][1])
                self.stdout.write(f"{stage}: {upserted} upserted, {cur.rowcount} removed")
                cur.execute(f"DROP TABLE {stage}")

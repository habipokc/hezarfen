"""Live and historical aircraft state.

The Go ingest service writes to these tables directly (ICD §3), so every table name
is pinned with Meta.db_table and column names follow the model field names.
"""

from django.contrib.gis.db import models
from django.contrib.postgres.indexes import BrinIndex


class Source(models.TextChoices):
    LIVE = "live"
    REPLAY = "replay"
    SYNTHETIC = "synthetic"


class Aircraft(models.Model):
    """Identity of an aircraft; one row per icao24 ever seen."""

    icao24 = models.CharField(max_length=6, primary_key=True)
    callsign = models.CharField(max_length=8, null=True, blank=True)
    origin_country = models.CharField(max_length=64, null=True, blank=True)
    # OpenSky emitter category (0-20); null when the source doesn't report it
    category = models.SmallIntegerField(null=True, blank=True)
    first_seen = models.DateTimeField()
    last_seen = models.DateTimeField(db_index=True)

    class Meta:
        db_table = "aircraft"
        verbose_name_plural = "aircraft"

    def __str__(self) -> str:
        return f"{self.icao24} {self.callsign or ''}".strip()


class StateFields(models.Model):
    """Measurement columns shared by the latest-state and history tables (ICD §2 units)."""

    ts = models.DateTimeField()
    geom = models.PointField(srid=4326)  # spatial_index=True by default -> GiST
    baro_altitude = models.FloatField(null=True, blank=True)  # m
    geo_altitude = models.FloatField(null=True, blank=True)  # m
    velocity = models.FloatField(null=True, blank=True)  # m/s
    heading = models.FloatField(null=True, blank=True)  # degrees from true north
    vertical_rate = models.FloatField(null=True, blank=True)  # m/s, + is climbing
    # db_default, not default: Django applies `default` in Python, but ingest inserts with
    # raw SQL, so the default has to live in the column definition itself
    on_ground = models.BooleanField(db_default=False)
    squawk = models.CharField(max_length=4, null=True, blank=True)
    source = models.CharField(max_length=10, choices=Source.choices, db_default=Source.LIVE)

    class Meta:
        abstract = True


class AircraftLatest(StateFields):
    """Latest state per aircraft; ingest upserts here, the live map reads from here."""

    aircraft = models.OneToOneField(
        Aircraft, primary_key=True, db_column="icao24", on_delete=models.CASCADE
    )

    class Meta:
        db_table = "aircraft_latest"
        verbose_name_plural = "aircraft latest"
        indexes = [models.Index(fields=["ts"], name="aircraft_latest_ts_idx")]

    def __str__(self) -> str:
        return f"{self.aircraft_id} @ {self.ts:%H:%M:%S}"


class Position(StateFields):
    """Append-only position history.

    icao24 is deliberately not a foreign key: this is the hot insert path of a time
    series, and history must survive independently of the aircraft table.
    """

    id = models.BigAutoField(primary_key=True)
    icao24 = models.CharField(max_length=6)

    class Meta:
        db_table = "positions"
        constraints = [
            # Makes re-ingesting the same snapshot a no-op (ON CONFLICT DO NOTHING).
            # Its unique B-tree on (icao24, ts) also serves "track of one aircraft" queries,
            # so no separate (icao24, ts) index is needed.
            models.UniqueConstraint(fields=["icao24", "ts"], name="positions_icao24_ts_uniq"),
        ]
        indexes = [
            # Rows arrive in time order, so physical order ~ ts order: a BRIN index stores
            # only min/max ts per block range and stays tiny compared to a B-tree.
            BrinIndex(fields=["ts"], name="positions_ts_brin"),
        ]

    def __str__(self) -> str:
        return f"{self.icao24} @ {self.ts:%Y-%m-%d %H:%M:%S}"

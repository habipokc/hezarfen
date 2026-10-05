from django.contrib.gis.db import models


class Geofence(models.Model):
    class Kind(models.TextChoices):
        AIRPORT_BUFFER = "airport_buffer"
        USER_DRAWN = "user_drawn"

    name = models.CharField(max_length=128)
    geom = models.PolygonField(srid=4326)
    active = models.BooleanField(default=True)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.USER_DRAWN)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "geofences"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class GeofenceEvent(models.Model):
    """An aircraft entering or leaving a geofence; written by the relay (Phase 4)."""

    class Event(models.TextChoices):
        ENTER = "enter"
        EXIT = "exit"

    geofence = models.ForeignKey(Geofence, on_delete=models.CASCADE, related_name="events")
    icao24 = models.CharField(max_length=6)
    event = models.CharField(max_length=5, choices=Event.choices)
    ts = models.DateTimeField()
    geom = models.PointField(srid=4326)  # where the aircraft was when the event fired

    class Meta:
        db_table = "geofence_events"
        ordering = ["-ts"]
        indexes = [
            models.Index(fields=["ts"], name="geofence_events_ts_idx"),
            models.Index(fields=["geofence", "ts"], name="geofence_events_fence_ts_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.icao24} {self.event} {self.geofence_id}"

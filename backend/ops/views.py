"""/api/health and the server-rendered ops panel (/ops/, Django templates + HTMX).

The panel is hypermedia: every endpoint returns HTML. Full page on /ops/; the other
endpoints return one fragment that HTMX swaps in place of the element that asked for it.
"""

import redis
from django.conf import settings
from django.db import connection
from django.db.models import OuterRef, Subquery
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from geofencing.api import publish_on_commit
from geofencing.models import Geofence, GeofenceEvent
from tracking.models import Aircraft, AircraftLatest
from tracking.retention import last_run, prune_positions, record_run

from .ingest import fetch_ingest_metrics, ingest_summary

EVENT_ROWS = 50


def health(request):
    """Liveness + dependency check used by the compose healthcheck and nginx smoke tests."""
    checks: dict[str, str] = {}
    healthy = True

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT postgis_lib_version()")
            checks["postgis"] = cursor.fetchone()[0]
    except Exception as exc:  # report, don't crash: the endpoint must always answer
        checks["postgis"] = f"error: {exc.__class__.__name__}"
        healthy = False

    try:
        redis.Redis.from_url(settings.REDIS_URL, socket_timeout=2).ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc.__class__.__name__}"
        healthy = False

    return JsonResponse(
        {"status": "ok" if healthy else "degraded", "checks": checks},
        status=200 if healthy else 503,
    )


# ------------------------------------------------------------------------- context


def ingest_context() -> dict:
    now = timezone.now()
    cutoff = now - timezone.timedelta(seconds=settings.LIVE_WINDOW_SECONDS)
    return {
        "ingest": ingest_summary(fetch_ingest_metrics(), now),
        "active_aircraft": AircraftLatest.objects.filter(ts__gte=cutoff).count(),
        "events_last_hour": GeofenceEvent.objects.filter(
            ts__gte=now - timezone.timedelta(hours=1)
        ).count(),
    }


def events_context() -> dict:
    events = (
        GeofenceEvent.objects.select_related("geofence")
        .annotate(
            callsign=Subquery(
                Aircraft.objects.filter(icao24=OuterRef("icao24")).values("callsign")[:1]
            )
        )
        .order_by("-ts", "-id")[:EVENT_ROWS]
    )
    return {"events": list(events), "event_rows": EVENT_ROWS, "now": timezone.now()}


def positions_overview() -> dict:
    """Size and age of the history without scanning it: a COUNT(*) or MIN(ts) over tens of
    millions of rows would take seconds, and the BRIN index cannot answer MIN."""
    with connection.cursor() as cursor:
        # planner statistics, refreshed by (auto)ANALYZE; -1 until the first one
        cursor.execute("SELECT reltuples::bigint FROM pg_class WHERE oid = 'positions'::regclass")
        estimate = cursor.fetchone()[0]
        # append-only table: the smallest id is the oldest insert, found via the primary key
        cursor.execute("SELECT ts FROM positions ORDER BY id LIMIT 1")
        row = cursor.fetchone()
    return {"estimate": estimate if estimate >= 0 else None, "oldest": row[0] if row else None}


def retention_context(result=None) -> dict:
    return {
        "retention_days": settings.POSITIONS_RETENTION_DAYS,
        "retention_interval": settings.RETENTION_INTERVAL_SECONDS,
        "last_run": last_run(),
        "positions": positions_overview(),
        "result": result,
        "now": timezone.now(),
    }


# ------------------------------------------------------------------------- views


@require_GET
def index(request):
    context = {
        **ingest_context(),
        **events_context(),
        **retention_context(),
        "geofences": Geofence.objects.all(),
    }
    return render(request, "ops/index.html", context)


@require_GET
def ingest_partial(request):
    return render(request, "ops/_ingest.html", ingest_context())


@require_GET
def events_partial(request):
    return render(request, "ops/_events.html", events_context())


@require_POST
def geofence_active(request, pk: int):
    """Set (not toggle) the active flag: a double click or a retried request sends the same
    value again and changes nothing, where a toggle would flip it back."""
    value = request.POST.get("active")
    if value not in ("true", "false"):
        return HttpResponseBadRequest("active must be 'true' or 'false'")
    fence = get_object_or_404(Geofence, pk=pk)
    active = value == "true"
    if fence.active != active:
        fence.active = active
        fence.save(update_fields=["active"])
        # same notification as PATCH /api/geofences/{id}/: the relay reloads its fences
        publish_on_commit(fence.id, "updated")
    return render(request, "ops/_geofence_row.html", {"fence": fence})


@require_http_methods(["GET", "POST"])
def retention(request):
    result = None
    if request.method == "POST":
        result = prune_positions()
        record_run(result, trigger="manual")
    return render(request, "ops/_retention.html", retention_context(result))

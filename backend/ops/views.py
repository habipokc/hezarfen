import redis
from django.conf import settings
from django.db import connection
from django.http import JsonResponse


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

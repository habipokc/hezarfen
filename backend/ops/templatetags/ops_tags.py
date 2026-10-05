from datetime import datetime

from django import template

from ops.ingest import format_age

register = template.Library()


@register.filter
def age(seconds: float | None) -> str:
    """Seconds as a compact duration: {{ ingest.uptime|age }} -> "2 h 5 min"."""
    return format_age(seconds)


@register.filter
def ago(moment: datetime | None, now: datetime) -> str:
    """{{ event.ts|ago:now }} -> "12 s"; "never" for None."""
    return format_age(None if moment is None else (now - moment).total_seconds())

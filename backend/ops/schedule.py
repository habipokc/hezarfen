"""A deliberately small scheduler: one job, one interval, one thread.

Enough for hourly retention; a cron daemon, Celery beat or pg_cron would each add a moving
part this project does not need yet (DECISIONS D-084).
"""

import logging
from collections.abc import Callable
from typing import Protocol

log = logging.getLogger(__name__)


class Stopper(Protocol):
    def wait(self, timeout: float) -> bool: ...


def run_every(
    job: Callable[[], object],
    interval: float,
    stop: Stopper,
    first_delay: float = 0,
    after_run: Callable[[], object] | None = None,
) -> None:
    """Run `job` after `first_delay` seconds, then every `interval` seconds, until `stop`
    (a threading.Event) is set. Waiting on the event instead of sleeping means SIGTERM ends
    the loop at once instead of after up to an hour. A failing run is logged and retried at
    the next tick: a database restart must not end retention for good."""
    delay = first_delay
    while not stop.wait(delay):
        try:
            job()
        except Exception:
            log.exception("scheduled job failed")
        if after_run is not None:
            after_run()
        delay = interval

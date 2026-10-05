import threading

from ops.schedule import run_every


class FakeStop:
    """Stands in for threading.Event: `wait` returns at once and reports "stopped" from the
    `stop_after`-th call on, recording every timeout it was asked to wait."""

    def __init__(self, stop_after):
        self.stop_after = stop_after
        self.waits = []

    def wait(self, timeout):
        self.waits.append(timeout)
        return len(self.waits) >= self.stop_after


def test_runs_at_start_then_every_interval():
    runs = []
    stop = FakeStop(stop_after=3)
    run_every(lambda: runs.append(1), 3600, stop)
    assert len(runs) == 2
    assert stop.waits == [0, 3600, 3600]


def test_first_run_can_be_delayed():
    stop = FakeStop(stop_after=2)
    run_every(lambda: None, 3600, stop, first_delay=30)
    assert stop.waits == [30, 3600]


def test_a_failing_run_does_not_end_the_loop():
    calls = []

    def job():
        calls.append(1)
        raise RuntimeError("database went away")

    run_every(job, 10, FakeStop(stop_after=4))
    assert len(calls) == 3


def test_does_not_run_when_already_stopped():
    runs = []
    run_every(lambda: runs.append(1), 10, FakeStop(stop_after=1))
    assert runs == []


def test_a_real_event_stops_it():
    stop = threading.Event()
    runs = []

    def job():
        runs.append(1)
        stop.set()  # e.g. SIGTERM arriving during a run

    run_every(job, 3600, stop)
    assert runs == [1]


def test_after_each_run_hook():
    beats = []
    run_every(lambda: None, 10, FakeStop(stop_after=3), after_run=lambda: beats.append(1))
    assert len(beats) == 2

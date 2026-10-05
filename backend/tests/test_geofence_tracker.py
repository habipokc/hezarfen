from geofencing.tracker import ENTER, EXIT, GeofenceTracker

A, B = "aaaaaa", "bbbbbb"


def test_entering_produces_one_enter():
    t = GeofenceTracker()
    assert t.update([A], [(A, 1)]) == [(A, 1, ENTER)]


def test_staying_inside_produces_no_duplicate_enter():
    t = GeofenceTracker()
    t.update([A], [(A, 1)])
    assert t.update([A], [(A, 1)]) == []
    assert t.update([A], [(A, 1)]) == []


def test_leaving_produces_exit_and_reentry_produces_enter_again():
    t = GeofenceTracker()
    t.update([A], [(A, 1)])
    assert t.update([A], []) == [(A, 1, EXIT)]
    assert t.update([A], []) == []
    assert t.update([A], [(A, 1)]) == [(A, 1, ENTER)]


def test_absent_from_batch_is_not_an_exit():
    t = GeofenceTracker()
    t.update([A, B], [(A, 1), (B, 1)])
    assert t.update([B], [(B, 1)]) == []
    assert t.inside_pairs() == {(A, 1), (B, 1)}


def test_moving_between_overlapping_fences():
    t = GeofenceTracker()
    assert t.update([A], [(A, 1)]) == [(A, 1, ENTER)]
    assert t.update([A], [(A, 1), (A, 2)]) == [(A, 2, ENTER)]
    assert t.update([A], [(A, 2)]) == [(A, 1, EXIT)]


def test_events_are_ordered_exit_before_enter():
    t = GeofenceTracker()
    t.update([A], [(A, 2)])
    assert t.update([A], [(A, 1)]) == [(A, 2, EXIT), (A, 1, ENTER)]


def test_forget_drops_state_silently():
    t = GeofenceTracker()
    t.update([A], [(A, 1)])
    t.forget(A)
    assert t.inside_pairs() == set()
    assert t.update([A], [(A, 1)]) == [(A, 1, ENTER)]


def test_prune_drops_removed_fences_without_events():
    t = GeofenceTracker()
    t.update([A, B], [(A, 1), (A, 2), (B, 2)])
    t.prune(active_ids={1})
    assert t.inside_pairs() == {(A, 1)}
    assert t.update([A, B], [(A, 1)]) == []


def test_load_restores_state_so_restart_does_not_duplicate_enter():
    t = GeofenceTracker()
    t.load([(A, 1)])
    assert t.update([A], [(A, 1)]) == []
    assert t.update([A], []) == [(A, 1, EXIT)]

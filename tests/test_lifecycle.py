"""Behaviour of ``ApplicationLifecycle``: health gating and the tracking tick.

One tracking tick gets a frame, the visible windows and a point of regard (PoR), works out
which window the PoR falls on, and stores one row. These tests run real ticks of
``monitor_focus`` against fake services and a temporary database and only look at what
gets stored, so they keep passing if the loop is restructured (for example into a
``tick()`` method), as long as the recorded result is the same.
"""

from datetime import datetime
from unittest.mock import patch

import pytest

from tests.conftest import monitor, stored_rows, window


class _StopLoop(Exception):
    pass


def run_ticks(lc, ticks=1):
    """Run ``monitor_focus`` for exactly ``ticks`` ticks.

    The loop runs forever, so the health check, which runs at the start of every tick,
    raises after the requested number of ticks.
    """
    calls = {"n": 0}

    def check_services(*_, **__):
        calls["n"] += 1
        if calls["n"] > ticks:
            raise _StopLoop

    lc.check_services = check_services
    lc.now = datetime.min
    with pytest.raises(_StopLoop):
        lc.monitor_focus()


EDITOR = window("code.exe", (0, 0, 1200, 1080), z=1, title="main.py")
BROWSER = window("chrome.exe", (800, 0, 1920, 1080), z=0, title="Docs")


def test_records_window_under_point_of_regard(make_lifecycle, tracker_store):
    """A PoR inside a window stores that window's process name and title.

    Why: this is the system's core output. One row per tick says what the user looked at.
    """
    lc = make_lifecycle(windows=[EDITOR, BROWSER], por=(300, 500))

    run_ticks(lc)

    assert stored_rows(tracker_store) == [("code.exe", "main.py")]


def test_front_window_wins_where_windows_overlap(make_lifecycle, tracker_store):
    """A PoR where two windows overlap is attributed to the one in front.

    Why: only the front window is visible at that point. Attributing by z-order is what
    makes overlapping layouts (the normal case on a desktop) report correctly.
    """
    lc = make_lifecycle(windows=[EDITOR, BROWSER], por=(1000, 500))

    run_ticks(lc)

    assert stored_rows(tracker_store) == [("chrome.exe", "Docs")]


def test_point_of_regard_is_relative_to_tracked_monitor(make_lifecycle, tracker_store):
    """PoR coordinates are offset by the tracked monitor's position before matching windows.

    Why: calibration happens in monitor-local pixels, while the watchdog reports windows in
    absolute desktop coordinates. Here the tracked monitor sits to the right of the primary,
    so local (100, 100) is absolute (2020, 100).
    """
    right_monitor = monitor(x=1920, y=0)
    on_primary = window("explorer.exe", (0, 0, 1920, 1080), z=0)
    on_right = window("slack.exe", (1920, 0, 3840, 1080), z=1)
    lc = make_lifecycle(mon=right_monitor, windows=[on_primary, on_right], por=(100, 100))

    run_ticks(lc)

    assert stored_rows(tracker_store) == [("slack.exe", "slack.exe window")]


def test_no_point_of_regard_records_a_gap(make_lifecycle, tracker_store):
    """When the vision service returns no PoR, an empty row is still stored.

    Why: recording gaps (user away, face not visible) keeps a record that tracking was
    running but couldn't attribute attention. The dashboard skips empty rows when
    totalling time per app.
    """
    lc = make_lifecycle(windows=[EDITOR], por=(None, None))

    run_ticks(lc)

    assert stored_rows(tracker_store) == [("", "")]


@pytest.mark.xfail(
    strict=True,
    reason="Known bug on develop: _determine_viewed_window_info returns None and monitor_focus "
    "indexes it. Fixed on multi-monitor-support (1b78d0a).",
)
def test_point_of_regard_outside_all_windows_records_a_gap(make_lifecycle, tracker_store):
    """A PoR that falls on no window (bare desktop, or calibration drift off-screen) stores a gap.

    Why: the tracking loop must survive any prediction the vision service can return. One
    unlucky prediction shouldn't stop tracking.
    """
    lc = make_lifecycle(windows=[window("code.exe", (0, 0, 100, 100), z=0)], por=(900, 900))

    run_ticks(lc)

    assert stored_rows(tracker_store) == [("", "")]


def test_each_tick_stores_one_row(make_lifecycle, tracker_store):
    """Every tick stores exactly one row.

    Why: the dashboard derives time spent from the spacing between rows. Extra or missing
    rows directly distort the reported durations.
    """
    lc = make_lifecycle(windows=[EDITOR], por=(10, 10))

    run_ticks(lc, ticks=3)

    assert len(stored_rows(tracker_store)) == 3


class TestHealthGate:
    """``check_services`` blocks until all three services report healthy."""

    def _lc(self, make_lifecycle, statuses):
        lc = make_lifecycle()
        lc.period = 0
        lc.vision_tracking_client.get_service_status = lambda: statuses["vision"]
        lc.windows_webcam_client.get_service_status = lambda: statuses["webcam"]
        lc.system_watchdog_client.get_service_status = lambda: statuses["watchdog"]
        return lc

    def test_passes_when_all_services_are_healthy(self, make_lifecycle):
        """All services healthy: returns immediately.

        Why: tracking needs all three inputs; there's no degraded mode today.
        """
        lc = self._lc(make_lifecycle, {"vision": True, "webcam": True, "watchdog": True})

        assert lc.check_services(max_retries=1) is True

    @pytest.mark.parametrize("down", ["vision", "webcam", "watchdog"])
    def test_raises_after_max_retries_if_any_service_is_down(self, make_lifecycle, down):
        """Any one service down: retries, then raises once ``max_retries`` is reached.

        Why: services start independently (Windows logon task, Docker) and often come up after
        the orchestrator, so it waits for them. A bounded retry count lets callers give up.
        """
        statuses = {"vision": True, "webcam": True, "watchdog": True, down: False}
        lc = self._lc(make_lifecycle, statuses)

        with pytest.raises(Exception, match="Health Check Failed"):
            lc.check_services(max_retries=3)

    def test_recovers_when_service_comes_up(self, make_lifecycle):
        """A service that is down at first and then comes up lets startup continue.

        Why: this is the normal startup race described above.
        """
        answers = iter([False, False, True])
        lc = self._lc(make_lifecycle, {"vision": True, "webcam": True, "watchdog": True})
        lc.vision_tracking_client.get_service_status = lambda: next(answers)

        with patch("src.backend.lifecycle.time.sleep"):
            assert lc.check_services(max_retries=5) is True

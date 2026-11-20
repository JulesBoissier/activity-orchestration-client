"""Behaviour of the tracking tick and the lifecycle around it.

One tick gets a frame, the visible windows and a point of regard (PoR), works out which
window the PoR falls on, and stores one row. These tests run real ticks (``tracker.tick()``)
against fake services and a temporary database and look only at what gets stored.
"""

import threading
import time
from unittest.mock import patch

import pytest

from src.backend.attribution import CAMERA_UNAVAILABLE, NO_FACE, NO_WINDOW, TICK_FAILED
from tests.conftest import monitor, stored_gap_reasons, stored_rows, window


def run_ticks(lc, ticks=1):
    """Take exactly ``ticks`` samples."""
    for _ in range(ticks):
        lc.tracker.tick()


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


def test_point_of_regard_outside_all_windows_records_a_gap(make_lifecycle, tracker_store):
    """A PoR that falls on no window (bare desktop, or calibration drift off-screen) stores a gap.

    Why: the tracking loop must survive any prediction the vision service can return. One
    unlucky prediction shouldn't stop tracking.
    """
    lc = make_lifecycle(windows=[window("code.exe", (0, 0, 100, 100), z=0)], por=(900, 900))

    run_ticks(lc)

    assert stored_rows(tracker_store) == [("", "")]


def test_no_camera_frame_records_a_gap(make_lifecycle, tracker_store):
    """When the webcam service has no frame (camera unplugged or busy), a gap row is stored.

    Why: a temporarily unavailable camera mustn't stop tracking or crash the loop.
    """
    lc = make_lifecycle(windows=[EDITOR], por=(300, 500))
    lc.windows_webcam_client.frame = None

    run_ticks(lc)

    assert stored_rows(tracker_store) == [("", "")]


@pytest.mark.parametrize(
    "case,expected",
    [("camera", CAMERA_UNAVAILABLE), ("face", NO_FACE), ("window", NO_WINDOW), ("hit", None)],
)
def test_each_sample_records_why_it_is_a_gap(make_lifecycle, tracker_store, case, expected):
    """Gap rows record their reason: camera unavailable, no face, or no window at the point.

    Why: "the camera was broken for an hour" and "I was away for an hour" both produce empty
    rows. The reason tells them apart. Samples on a window have no reason.
    """
    por = {"face": (None, None), "window": (1900, 1000)}.get(case, (300, 500))
    lc = make_lifecycle(windows=[window("code.exe", (0, 0, 1200, 1040), z=0)], por=por)
    if case == "camera":
        lc.windows_webcam_client.frame = None

    run_ticks(lc)

    assert stored_gap_reasons(tracker_store) == [expected]


def test_no_camera_frame_skips_the_other_services(make_lifecycle):
    """Without a camera frame, the tick doesn't query the watchdog or the vision service.

    Why: the sample is a gap whatever they answer, so the requests would be wasted every
    tick for as long as the camera is down.
    """
    lc = make_lifecycle(windows=[EDITOR], por=(300, 500))
    lc.windows_webcam_client.frame = None
    lc.system_watchdog_client.get_windows_info = lambda: pytest.fail("watchdog queried")
    lc.vision_tracking_client.predict_por = lambda image: pytest.fail("vision queried")

    result = lc.tracker.tick()

    assert result.attribution.gap_reason == CAMERA_UNAVAILABLE


def test_tracking_survives_a_failing_tick_and_stops_on_request(make_lifecycle, tracker_store):
    """A tick that raises is recorded as a "tick failed" gap and tracking carries on; ``stop()`` ends it.

    Why: a service restarting used to raise out of the loop and end tracking until someone
    restarted the orchestrator. Recording the failure keeps it visible on the timeline.
    """
    lc = make_lifecycle(windows=[EDITOR], por=(300, 500))
    calls = {"n": 0}
    real = lc.system_watchdog_client.get_windows_info

    def flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            raise ConnectionError("watchdog restarting")
        return real()

    lc.system_watchdog_client.get_windows_info = flaky
    loop = threading.Thread(target=lc.monitor_focus)
    loop.start()
    deadline = time.monotonic() + 5
    while len(stored_rows(tracker_store)) < 3 and time.monotonic() < deadline:
        time.sleep(0.01)
    lc.stop()
    loop.join(2)

    assert not loop.is_alive()
    reasons = stored_gap_reasons(tracker_store)
    assert reasons[0] == TICK_FAILED
    assert stored_rows(tracker_store)[1] == ("code.exe", "main.py")


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

"""Behaviour of ``attribute``: which window a point of regard falls on."""

import pytest

from src.backend.attribution import NO_FACE, NO_WINDOW, attribute
from tests.conftest import monitor


def visible(exe, rect, z, title="t"):
    """A window as ``SystemWatchdogClient.get_visible_windows`` returns it."""
    return {"exe_name": exe, "title": title, "z_index": z, "visible_rects": [list(rect)]}


@pytest.mark.parametrize("por", [None, [None, None], [10, None]])
def test_missing_point_of_regard_is_a_no_face_gap(por):
    """No point of regard means the vision service found no face (or no calibration).

    Why: the reason is stored with the gap, so "away from the desk" can be told apart from
    other gaps on the dashboard.
    """
    result = attribute(por, [visible("code.exe", (0, 0, 100, 100), 0)], monitor())

    assert result.is_gap and result.gap_reason == NO_FACE
    assert result.process_name == ""


def test_point_on_a_window_is_attributed_to_it():
    """A point inside a window's visible area is attributed to that window.

    Why: the core output of the system.
    """
    result = attribute([50, 50], [visible("code.exe", (0, 0, 100, 100), 0, "main.py")], monitor())

    assert (result.process_name, result.window_title, result.is_gap) == ("code.exe", "main.py", False)


def test_point_between_windows_is_a_no_window_gap():
    """A point on bare desktop (no visible window) is a gap with its own reason.

    Why: looking at the desktop isn't time spent in any app, but it isn't "no face" either.
    """
    result = attribute([500, 500], [visible("code.exe", (0, 0, 100, 100), 0)], monitor())

    assert result.gap_reason == NO_WINDOW


def test_point_is_offset_by_the_tracked_monitor():
    """Monitor-relative points are converted to desktop coordinates before matching.

    Why: calibration and prediction use the tracked monitor's local pixels; the watchdog
    reports windows in absolute desktop pixels.
    """
    right = monitor(x=1920)
    windows = [visible("left.exe", (0, 0, 1920, 1080), 0), visible("right.exe", (1920, 0, 3840, 1080), 1)]

    assert attribute([10, 10], windows, right).process_name == "right.exe"


def test_window_without_exe_name_is_still_attributed():
    """A window whose process couldn't be inspected (exe_name null) still counts, with an empty name.

    Why: the watchdog reports protected processes without an exe name. Treating them as a
    gap would hide time spent in elevated apps entirely.
    """
    result = attribute([5, 5], [visible(None, (0, 0, 100, 100), 0, "Task Manager")], monitor())

    assert result.window_title == "Task Manager" and not result.is_gap

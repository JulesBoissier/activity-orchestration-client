"""Behaviour of ``MonitorUtility``: monitor selection, calibration grids and screen regions.

The tests describe a three-monitor desk (one monitor left of the primary at negative x and
one right of it, offset vertically) so multi-monitor arithmetic is exercised headless.
"""

from unittest.mock import patch

import pytest

from src.backend.screen_region import MonitorUtility
from tests.conftest import monitor

LEFT = monitor(-1920, 0, 1920, 1080, "LEFT")
PRIMARY = monitor(0, 0, 2560, 1440, "PRIMARY")
RIGHT = monitor(2560, 200, 1920, 1080, "RIGHT")
DESK = [PRIMARY, LEFT, RIGHT]  # Windows lists the primary first


@pytest.fixture
def desk():
    with patch("src.backend.screen_region.get_monitors", return_value=DESK):
        yield


def inside(point, x, y, w, h):
    return x <= point[0] <= x + w and y <= point[1] <= y + h


def test_selects_monitor_by_one_based_index(desk):
    """Index 1 is the first monitor reported by the OS (the primary on Windows).

    Why: users pick a monitor by number. One-based indices match Windows display settings.
    """
    assert MonitorUtility.select_monitor(1) is PRIMARY
    assert MonitorUtility.select_monitor(3) is RIGHT


@pytest.mark.parametrize("bad_index", [0, 4, -1])
def test_invalid_index_falls_back_to_primary(desk, bad_index):
    """An out-of-range index selects the primary monitor instead of failing.

    Why: monitors get unplugged. Tracking on the primary is better than not starting.
    """
    assert MonitorUtility.select_monitor(bad_index) is PRIMARY


def test_no_index_selects_whole_desktop(desk):
    """``select_monitor(None)`` returns a virtual monitor bounding every display.

    Why: multi-monitor tracking calibrates and predicts in one coordinate space covering all
    monitors. Its origin is the desktop's top-left corner, which can be negative.
    """
    virtual = MonitorUtility.select_monitor(None)

    assert (virtual.x, virtual.y) == (-1920, 0)
    assert (virtual.width, virtual.height) == (1920 + 2560 + 1920, 1440)


def test_calibration_grid_spans_single_monitor():
    """A resolution-3 grid has 9 points in monitor-local pixels, reaching all four edges.

    Why: IDW predictions can't leave the area spanned by calibration points (see the vision
    service tests), so the grid has to reach the edges for edge windows to be trackable.
    """
    points = MonitorUtility.create_positions_list(PRIMARY, 3)

    assert len(points) == 9
    assert all(inside(p, 0, 0, 2560, 1440) for p in points)
    xs, ys = {p[0] for p in points}, {p[1] for p in points}
    assert min(xs) == 0 and max(xs) >= 2560 - 2
    assert min(ys) == 0 and max(ys) >= 1440 - 2
    assert (1280, 720) in points


def test_multi_monitor_grid_covers_every_monitor(desk):
    """On the virtual desktop, each monitor gets its own full grid, in virtual coordinates.

    Why: a single grid over the bounding box would put dots in dead zones between
    differently sized monitors, and skip their edges. Coordinates are relative to the
    virtual monitor's origin, the same space the tracking loop converts back from.
    """
    virtual = MonitorUtility.select_monitor(None)

    points = MonitorUtility.create_positions_list(virtual, 3)

    assert len(points) == 9 * len(DESK)
    for m in DESK:
        local_x, local_y = m.x - virtual.x, m.y - virtual.y
        on_monitor = [p for p in points if inside(p, local_x, local_y, m.width, m.height)]
        assert len(on_monitor) >= 9, m.name


def test_quadrant_lookup():
    """``find_screen_region`` returns the quadrant containing a point, or ``None`` off-monitor.

    Why: quadrant accuracy is the coarse metric the accuracy test reports alongside RMSE.
    Points off the monitor must not be counted as a hit.
    """
    regions = MonitorUtility.create_screen_region_list(PRIMARY, 2)

    assert MonitorUtility.find_screen_region(10, 10, PRIMARY, 2) == regions[0]
    assert MonitorUtility.find_screen_region(2500, 1400, PRIMARY, 2) == regions[3]
    assert MonitorUtility.find_screen_region(3000, 10, PRIMARY, 2) is None


def test_supplied_layout_is_used_without_asking_the_os():
    """With an explicit monitor list, selection and calibration grids never query ``screeninfo``.

    Why: the orchestrator now takes the layout from the watchdog (Windows' view). Mixing in
    this machine's view (WSLg) would put calibration dots and window rects in different
    coordinate systems whenever the two disagree.
    """
    with patch("src.backend.screen_region.get_monitors", side_effect=AssertionError("queried the OS")):
        virtual = MonitorUtility.select_monitor(None, monitors=DESK)
        points = MonitorUtility.create_positions_list(virtual, 3)
        second = MonitorUtility.select_monitor(2, monitors=DESK)

    assert (virtual.x, virtual.width) == (-1920, 6400)
    assert len(points) == 27
    assert second is LEFT

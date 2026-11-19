"""Behaviour of ``SystemWatchdogClient`` window visibility (clipping and occlusion).

The watchdog service reports raw window rectangles and z-order. The client works out which
part of each window is actually visible on the tracked monitor. Doing this on the client
keeps the Windows service thin and lets this geometry be tested on any OS.
"""

import pytest

from src.backend.clients.system_watchdog_client import SystemWatchdogClient
from tests.conftest import monitor, window


@pytest.fixture
def client():
    return SystemWatchdogClient("127.0.0.1", 8002)


def by_exe(results):
    return {w["exe_name"]: w for w in results}


def test_front_window_is_fully_visible_and_hides_what_it_covers(client):
    """The front window keeps its full area; a window behind it loses the overlapped part.

    Why: attribution must only match a PoR against pixels the user can actually see.
    """
    back = window("code.exe", (0, 0, 1000, 1000), z=1)
    front = window("chrome.exe", (500, 0, 1500, 1000), z=0)

    result = by_exe(client.compute_visible_windows([back, front], monitor=monitor()))

    assert result["chrome.exe"]["visible_area"] == 1000 * 1000
    assert result["chrome.exe"]["visible_fraction"] == pytest.approx(1.0)
    assert result["code.exe"]["visible_area"] == 500 * 1000
    assert result["code.exe"]["visible_fraction"] == pytest.approx(0.5)
    assert result["code.exe"]["visible_rects"] == [[0, 0, 500, 1000]]


def test_fully_covered_window_is_dropped(client):
    """A window entirely hidden behind others doesn't appear in the result.

    Why: a hidden window can never be what the user is looking at. Dropping it also keeps
    the per-tick list short.
    """
    hidden = window("notepad.exe", (100, 100, 200, 200), z=1)
    maximised = window("chrome.exe", (0, 0, 1920, 1080), z=0)

    result = by_exe(client.compute_visible_windows([hidden, maximised], monitor=monitor()))

    assert set(result) == {"chrome.exe"}


@pytest.mark.parametrize(
    "rect",
    [
        (-32000, -32000, -31840, -31972),  # how Windows reports minimised windows
        (2000, 0, 3840, 1080),  # entirely on another monitor
        pytest.param(
            (1920, 0, 3840, 1080),  # maximised on the next monitor, sharing an edge
            marks=pytest.mark.xfail(
                strict=True,
                reason="Known bug: a shared edge clips to a zero-area line, which is not "
                "'empty', so the window is reported with visible_area 0.",
            ),
        ),
    ],
)
def test_windows_off_the_tracked_monitor_are_ignored(client, rect):
    """Minimised windows and windows on other monitors aren't reported as visible.

    Why: they can't contain the PoR on the tracked monitor, and minimised windows report
    nonsense coordinates.
    """
    result = client.compute_visible_windows(
        [window("app.exe", rect, z=0)], monitor=monitor(0, 0, 1920, 1080)
    )

    assert result == []


def test_windows_spanning_monitors_are_clipped(client):
    """A window straddling two monitors only counts the part on the tracked monitor.

    Why: in multi-monitor setups windows are often dragged across the boundary.
    """
    straddling = window("app.exe", (1500, 100, 2500, 500), z=0)

    (result,) = client.compute_visible_windows([straddling], monitor=monitor(0, 0, 1920, 1080))

    assert result["clipped_rect"] == [[1500, 100, 1920, 500]]
    assert result["visible_area"] == 420 * 400


def test_excluded_executables_neither_count_nor_occlude(client):
    """Executables in ``exclude_exe_names`` are removed before occlusion is computed.

    Why: some always-on-top surfaces (taskbar, overlays) would otherwise hide everything
    behind them without ever being a meaningful focus target.
    """
    overlay = window("overlay.exe", (0, 0, 1920, 1080), z=0)
    editor = window("code.exe", (0, 0, 1920, 1080), z=1)

    result = client.compute_visible_windows(
        [overlay, editor], monitor=monitor(), exclude_exe_names=["overlay.exe"]
    )

    assert [w["exe_name"] for w in result] == ["code.exe"]


@pytest.mark.parametrize("wrapped", [False, True])
def test_accepts_list_or_wrapped_payload(client, wrapped):
    """``get_visible_windows`` accepts both a bare list and ``{"windows": [...]}`` from the service.

    Why: the watchdog currently returns a bare list. The client tolerates a wrapper so the
    service can add metadata (monitors, timestamp) without a coordinated release.
    """
    windows = [window("code.exe", (0, 0, 100, 100), z=0)]
    client.get_windows_info = lambda: {"windows": windows} if wrapped else windows

    result = client.get_visible_windows(monitor=monitor())

    assert [w["exe_name"] for w in result] == ["code.exe"]

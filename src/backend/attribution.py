"""Deciding which window a point of regard falls on. Pure functions: no I/O, no state."""

from dataclasses import dataclass
from typing import Optional, Sequence

# Gap reasons, stored in the activity database's ``gap_reason`` column.
NO_FACE = "no face"
NO_WINDOW = "no window at point"
CAMERA_UNAVAILABLE = "camera unavailable"
TICK_FAILED = "tick failed"


@dataclass(frozen=True)
class Attribution:
    """What one sample was attributed to. An empty ``process_name`` means a gap."""

    process_name: str = ""
    window_title: str = ""
    gap_reason: Optional[str] = None  # set exactly when this is a gap

    @property
    def is_gap(self) -> bool:
        return self.gap_reason is not None


def find_window_at(abs_x: float, abs_y: float, visible_windows: Sequence[dict]) -> Optional[dict]:
    """The front-most visible window containing an absolute desktop point, or ``None``.

    ``visible_windows`` come from ``SystemWatchdogClient.get_visible_windows``: each has
    ``visible_rects`` (the parts not covered by windows in front) and a ``z_index``.
    """
    for window in sorted(visible_windows or [], key=lambda w: w.get("z_index", 0)):
        for left, top, right, bottom in window.get("visible_rects", []):
            if left <= abs_x < right and top <= abs_y < bottom:
                return window
    return None


def attribute(por, visible_windows: Sequence[dict], monitor) -> Attribution:
    """Attribute a point of regard (monitor-relative ``[x, y]``, or None/nulls) to a window."""
    if por is None or por[0] is None or por[1] is None:
        return Attribution(gap_reason=NO_FACE)
    window = find_window_at(monitor.x + por[0], monitor.y + por[1], visible_windows)
    if window is None:
        return Attribution(gap_reason=NO_WINDOW)
    return Attribution(
        process_name=window.get("exe_name") or window.get("name") or "",
        window_title=window.get("title") or "",
    )

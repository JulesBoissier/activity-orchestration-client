"""Implicit calibration: turn the user's clicks into calibration points while tracking.

People look at what they click. For each new left click (from the watchdog's ``/clicks``)
inside the tracked area, the frames the camera took just before the click (webcam
``/frame_at``) are sent to the vision service as an *implicit* calibration point. The
vision service keeps those per session, in a capped pool, so the calibration can follow
posture changes over the day.

Opt-in (``IMPLICIT_CALIBRATION=1``): without it nothing asks the watchdog for clicks, and
the watchdog only starts recording clicks when asked.
"""

import logging
from typing import Optional, Sequence

log = logging.getLogger(__name__)

# Frames from just before the click: people look at a target before (and while) clicking.
CLICK_FRAME_OFFSETS_S = (-0.2, -0.1, 0.0)


class ClickCalibrator:
    def __init__(self, watchdog, webcam, vision, monitor, max_clicks_per_tick: int = 2,
                 frame_offsets_s: Sequence[float] = CLICK_FRAME_OFFSETS_S):
        self.watchdog = watchdog
        self.webcam = webcam
        self.vision = vision
        self.monitor = monitor
        self.max_clicks_per_tick = max(1, int(max_clicks_per_tick))
        self.frame_offsets_s = tuple(frame_offsets_s)
        self.enabled = False
        self.last_seq: Optional[int] = None
        self.points_added = 0

    def start(self) -> bool:
        """Start click recording; clicks made before this are ignored. Returns whether it's on."""
        response = self.watchdog.get_clicks(after=0)
        if not response or not response.get("recording"):
            log.warning(
                "implicit calibration disabled: the watchdog can't record clicks "
                "(older watchdog without /clicks, or not running on Windows)"
            )
            self.enabled = False
            return False
        self.last_seq = int(response.get("last_seq", 0))
        self.enabled = True
        log.info("implicit calibration on: clicks become calibration points")
        return True

    def _local(self, x: float, y: float):
        """Click position relative to the tracked area, or None if it's outside every tracked monitor."""
        monitors = getattr(self.monitor, "monitors", None) or [self.monitor]
        if not any(m.x <= x < m.x + m.width and m.y <= y < m.y + m.height for m in monitors):
            return None
        return x - self.monitor.x, y - self.monitor.y

    def process_new_clicks(self) -> int:
        """Send the newest clicks since the last call as implicit points. Returns how many were added."""
        if not self.enabled:
            return 0
        response = self.watchdog.get_clicks(after=self.last_seq)
        if not response:
            return 0
        self.last_seq = int(response.get("last_seq", self.last_seq))
        # Only the most recent clicks: older ones may have left the webcam's frame history,
        # and each costs a vision-service request inside the tick.
        clicks = response.get("clicks", [])[-self.max_clicks_per_tick :]
        added = 0
        for click in clicks:
            local = self._local(click["x"], click["y"])
            if local is None:
                continue
            frames = [self.webcam.get_frame_at(click["t"] + dt) for dt in self.frame_offsets_s]
            frames = [f for f in frames if f is not None]
            if not frames:
                continue
            result = self.vision.add_calibration_point(local[0], local[1], frames, implicit=True)
            if result is True or (isinstance(result, dict) and result.get("added")):
                added += 1
        if added:
            self.points_added += added
            log.info("implicit calibration: %d click(s) added (%d this session)", added, self.points_added)
        return added

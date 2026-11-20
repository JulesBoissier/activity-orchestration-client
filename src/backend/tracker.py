"""One tracking sample: get the inputs, decide what was looked at, store it."""

import logging
import time
from dataclasses import dataclass
from typing import Optional, Sequence

from src.backend.attribution import CAMERA_UNAVAILABLE, Attribution, attribute

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TickResult:
    started_at: float  # time.monotonic() when the tick began
    por: Optional[Sequence]  # monitor-relative [x, y] from the vision service, if asked
    attribution: Attribution


class Tracker:
    """Takes one sample per ``tick()``. Knows nothing about timing or looping.

    The service clients are passed in, so tests and integration runs can use fakes or
    point real clients at the benchmark's replay servers.
    """

    def __init__(self, webcam, watchdog, vision, store, monitor):
        self.webcam = webcam
        self.watchdog = watchdog
        self.vision = vision
        self.store = store
        self.monitor = monitor

    def tick(self) -> TickResult:
        started = time.monotonic()
        frame = self.webcam.get_camera_jpeg()
        if frame is None:
            # Decided here, not by attribute(): only the tick knows about the camera. No
            # point asking the watchdog or the vision service for a sample that's a gap.
            por = None
            result = Attribution(gap_reason=CAMERA_UNAVAILABLE)
        else:
            windows = self.watchdog.get_visible_windows(monitor=self.monitor)
            por = self.vision.predict_por(frame)
            result = attribute(por, windows, self.monitor)

        self.store.save_attention(
            process_name=result.process_name,
            window_title=result.window_title,
            gap_reason=result.gap_reason,
        )
        if result.is_gap:
            log.info("gap: %s", result.gap_reason)
        else:
            log.info("viewed %s - %s", result.process_name, result.window_title)
        return TickResult(started, por, result)

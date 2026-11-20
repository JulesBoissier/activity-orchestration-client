"""Orchestrator settings: the only place that reads the environment (and ``.env``).

Everything else receives a ``Settings`` (or the values it needs) as an argument, so tests
and integration runs can configure the orchestrator without touching the environment.
Every variable is listed, with its default, in the workspace's ``.env.example``.
"""

import os
from dataclasses import dataclass
from typing import Mapping, Optional


@dataclass(frozen=True)
class ServiceAddress:
    host: str
    port: int


@dataclass(frozen=True)
class Settings:
    vision: ServiceAddress = ServiceAddress("127.0.0.1", 8000)
    webcam: ServiceAddress = ServiceAddress("127.0.0.1", 8001)
    watchdog: ServiceAddress = ServiceAddress("127.0.0.1", 8002)
    # Seconds between the starts of two tracking ticks.
    period_s: float = 2.0
    # 1-based monitor to track; None tracks all monitors as one virtual desktop.
    monitor_index: Optional[int] = None
    activity_db_url: str = "sqlite:///attention_tracker.db"
    # Frames per prediction (a short burst, ~33 ms apart). The vision service averages their
    # gaze features. On the benchmark, 3 frames cut the median error on three monitors by
    # ~6% (295 -> 277 px) and raised right-monitor attribution from 80% to 83%, at ~3x the
    # vision service's CPU per tick. Use 1 on a machine where a tick can't finish in time.
    frames_per_prediction: int = 3
    # Implicit calibration from clicks (off by default: unproven on the benchmark so far).
    # When on, the watchdog records clicks and each one inside the tracked area becomes a
    # session-only calibration point in the vision service.
    implicit_calibration: bool = False

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "Settings":
        """Read settings from ``env`` (default: the process environment, after loading ``.env``)."""
        if env is None:
            from dotenv import load_dotenv

            load_dotenv()
            env = os.environ

        def address(prefix: str, default: ServiceAddress) -> ServiceAddress:
            return ServiceAddress(
                env.get(f"{prefix}_IP", default.host),
                int(env.get(f"{prefix}_PORT", default.port)),
            )

        monitor = env.get("TRACKED_MONITOR_INDEX", "")
        return cls(
            vision=address("VISION_TRACKING_SERVICE", cls.vision),
            webcam=address("WINDOWS_WEBCAM_SERVICE", cls.webcam),
            watchdog=address("SYSTEM_WATCHDOG_SERVICE", cls.watchdog),
            period_s=float(env.get("TRACKING_PERIOD_S", cls.period_s)),
            monitor_index=int(monitor) if monitor.strip() else None,
            activity_db_url=env.get("ACTIVITY_DB_URL", cls.activity_db_url),
            frames_per_prediction=max(1, int(env.get("FRAMES_PER_PREDICTION", cls.frames_per_prediction))),
            implicit_calibration=env.get("IMPLICIT_CALIBRATION", "0").strip().lower()
            in ("1", "true", "yes", "on"),
        )

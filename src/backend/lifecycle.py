import logging
import threading
import time
from typing import Optional

from src.backend.attention_tracker_store import AttentionTrackerStore
from src.backend.attribution import TICK_FAILED
from src.backend.clients.system_watchdog_client import SystemWatchdogClient
from src.backend.clients.vision_tracking_client import VisionTrackingClient
from src.backend.clients.windows_webcam_client import WindowsWebcamClient
from src.backend.profile_manager import ProfileManager
from src.backend.scheduler import run_every
from src.backend.screen_region import MonitorUtility
from src.backend.tracker import Tracker
from src.backend.user_interfaces.performance_monitoring import PerformanceMonitoringGUI
from src.settings import Settings

log = logging.getLogger(__name__)


def _geometry(monitors):
    return sorted((m.x, m.y, m.width, m.height) for m in monitors)


class ApplicationLifecycle:
    """Startup (health checks, profile, optional accuracy test) then periodic tracking.

    Collaborators default to being built from ``settings``; pass them in to substitute
    fakes (tests) or point at other services (integration runs).
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        *,
        vision_tracking_client=None,
        windows_webcam_client=None,
        system_watchdog_client=None,
        attention_tracker_store=None,
        monitor=None,
    ):
        self.settings = settings or Settings.from_env()
        s = self.settings
        self.period = s.period_s
        self.vision_tracking_client = vision_tracking_client or VisionTrackingClient(
            s.vision.host, s.vision.port
        )
        self.windows_webcam_client = windows_webcam_client or WindowsWebcamClient(
            s.webcam.host, s.webcam.port
        )
        self.system_watchdog_client = system_watchdog_client or SystemWatchdogClient(
            s.watchdog.host, s.watchdog.port
        )
        self.attention_tracker_store = attention_tracker_store or AttentionTrackerStore(
            s.activity_db_url
        )
        self.monitor = monitor or MonitorUtility.select_monitor(
            s.monitor_index, monitors=self._monitor_layout()
        )

        self.profile_manager = ProfileManager(
            vision_tracking_client=self.vision_tracking_client,
            windows_webcam_client=self.windows_webcam_client,
            monitor=self.monitor,
        )
        self.tracker = Tracker(
            webcam=self.windows_webcam_client,
            watchdog=self.system_watchdog_client,
            vision=self.vision_tracking_client,
            store=self.attention_tracker_store,
            monitor=self.monitor,
            frames_per_prediction=s.frames_per_prediction,
        )
        self._stop = threading.Event()

    def _monitor_layout(self):
        """The monitors to track, as Windows sees them.

        Window rects come from the watchdog in Windows desktop coordinates, so monitor
        geometry should come from the same place. ``screeninfo`` here may see a different
        layout (WSLg scaling, DPI). If they disagree, the calibration GUI, which draws with
        this machine's display, may put dots in the wrong place: that's worth a warning.
        """
        remote = self.system_watchdog_client.get_monitors()
        try:
            from screeninfo import get_monitors

            local = get_monitors()
        except Exception:  # no display here (headless, CI)
            local = None
        if remote is None:
            log.warning("watchdog /get_monitors unavailable; using this machine's monitor layout")
            return local
        if local is not None and _geometry(local) != _geometry(remote):
            log.warning(
                "monitor layout differs between Windows %s and this display %s; using Windows'. "
                "Calibration dots may be misplaced (check display scaling).",
                _geometry(remote),
                _geometry(local),
            )
        return remote

    def check_services(self, max_retries: int = None):
        """Ensure that both services are running before proceeding."""
        attempts = 0

        while True:
            vision_tracking_client_ok = self.vision_tracking_client.get_service_status()
            windows_webcam_client_ok = self.windows_webcam_client.get_service_status()
            system_watchdog_client_ok = self.system_watchdog_client.get_service_status()

            if (
                vision_tracking_client_ok
                and windows_webcam_client_ok
                and system_watchdog_client_ok
            ):
                return True

            print(f"Global health-check failed. Re-trying in {self.period} seconds.")
            time.sleep(self.period)

            attempts += 1
            if max_retries is not None and attempts >= max_retries:
                raise Exception("Global Health Check Failed: Too many retries.")

    def run_performance_analysis(self):
        choice = input("Run performance analysis? [Y/N]: ")

        if choice.lower() == "y":
            nbr_of_samples = int(input("Number of samples to run analysis on:"))
            self._performance_analysis(nbr_of_samples=nbr_of_samples)
        elif choice.lower() == "n":
            return
        else:
            print("Invalid input. Please enter 'Y' or 'N'.")
            self.run_performance_analysis()

    def _performance_analysis(self, nbr_of_samples):
        pmg = PerformanceMonitoringGUI(
            self.monitor,
            nbr_of_samples,
            self.windows_webcam_client,
            self.vision_tracking_client,
            frames_per_prediction=self.settings.frames_per_prediction,
        )
        pmg.run()

    def _tracking_job(self):
        self.check_services()  # blocks (retrying) while a service is down
        self.tracker.tick()

    def _record_failed_tick(self, exc: Exception):
        """A tick raised: log it and record a gap, so the timeline shows tracking failed."""
        log.exception("tracking tick failed", exc_info=exc)
        try:
            self.attention_tracker_store.save_attention("", "", gap_reason=TICK_FAILED)
        except Exception:
            log.exception("could not record the failed tick")

    def monitor_focus(self):
        """Track until ``stop()`` is called: one tick every ``settings.period_s`` seconds."""
        self._stop.clear()
        run_every(self.period, self._tracking_job, self._stop, on_error=self._record_failed_tick)

    def stop(self):
        """Stop ``monitor_focus`` after the current tick."""
        self._stop.set()

    def run(self):
        """Start the application lifecycle."""
        self.check_services()
        self.profile_manager.select_or_create_profile()
        self.run_performance_analysis()
        self.monitor_focus()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ApplicationLifecycle().run()

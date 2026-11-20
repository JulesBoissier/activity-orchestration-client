"""Shared fixtures for the activity-orchestration-client test suite.

The orchestrator talks to three HTTP services. The tests never open a socket: service
clients are either replaced by in-memory fakes (lifecycle tests) or tested against a
mocked ``requests`` layer (client contract tests). Monitors are described by plain objects
so the suite runs headless, without ``screeninfo`` access to a real display.
"""

from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from src.backend.attention_tracker_store import AttentionTracker, AttentionTrackerStore


def monitor(x=0, y=0, width=1920, height=1080, name="DISPLAY1"):
    """A stand-in for ``screeninfo.Monitor`` with the attributes the code reads."""
    return SimpleNamespace(x=x, y=y, width=width, height=height, name=name)


def window(exe, rect, z, title=None):
    """One entry as returned by the watchdog's ``/windows_info`` route."""
    left, top, right, bottom = rect
    return {
        "hwnd": 1000 + z,
        "exe_name": exe,
        "title": title or f"{exe} window",
        "rect": [left, top, right, bottom],
        "size": [right - left, bottom - top],
        "z_index": z,
    }


def mjpeg_stream(frames, boundary=b"frame"):
    """Encode frames exactly like windows-webcam-service's ``/video_feed`` generator."""
    body = b""
    for frame in frames:
        ok, buf = cv2.imencode(".jpg", frame)
        assert ok
        body += (
            b"--" + boundary + b"\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n"
        )
    return body


class FakeWebcam:
    def __init__(self):
        self.frame = np.zeros((48, 64, 3), dtype=np.uint8)

    def get_service_status(self):
        return True

    def get_camera_input(self):
        return self.frame

    def get_camera_jpeg(self):
        if self.frame is None:
            return None
        return cv2.imencode(".jpg", self.frame)[1].tobytes()

    def get_camera_jpegs(self, count):
        frames = [self.get_camera_jpeg() for _ in range(count)]
        return [f for f in frames if f is not None]


class FakeVision:
    """Returns a fixed point of regard; ``None`` coordinates mean "no face"."""

    def __init__(self, por=(None, None)):
        self.por = por
        self.requests = []  # what each predict_por call received

    def get_service_status(self):
        return True

    def predict_por(self, image):
        self.requests.append(image)
        return list(self.por)


@pytest.fixture
def tracker_store(tmp_path):
    return AttentionTrackerStore(db_url=f"sqlite:///{tmp_path / 'attention.db'}")


def stored_rows(store):
    session = store.Session()
    try:
        return [
            (r.process_name, r.window_title)
            for r in session.query(AttentionTracker).order_by(AttentionTracker.id)
        ]
    finally:
        session.close()


def stored_gap_reasons(store):
    session = store.Session()
    try:
        return [r.gap_reason for r in session.query(AttentionTracker).order_by(AttentionTracker.id)]
    finally:
        session.close()


@pytest.fixture
def make_lifecycle(tracker_store):
    """Build an ``ApplicationLifecycle`` with fake services, a temp database and a given monitor.

    Collaborators are passed to the constructor; nothing is patched. The watchdog client is
    the real one (its clipping/occlusion is part of what a tick does) with only its HTTP
    call replaced.
    """
    from src.backend.clients.system_watchdog_client import SystemWatchdogClient
    from src.backend.lifecycle import ApplicationLifecycle
    from src.settings import Settings

    def build(mon=None, windows=(), por=(None, None)):
        watchdog = SystemWatchdogClient("127.0.0.1", 8002)
        watchdog.get_service_status = lambda: True
        watchdog.get_windows_info = lambda: list(windows)
        return ApplicationLifecycle(
            Settings(period_s=0.01),
            vision_tracking_client=FakeVision(por),
            windows_webcam_client=FakeWebcam(),
            system_watchdog_client=watchdog,
            attention_tracker_store=tracker_store,
            monitor=mon or monitor(),
        )

    return build

"""Implicit calibration: clicks during tracking become calibration points."""

from types import SimpleNamespace

from src.backend.implicit_calibration import ClickCalibrator
from tests.conftest import monitor


class FakeWatchdog:
    def __init__(self, recording=True):
        self.recording = recording
        self.clicks = []
        self.requests = []

    def click(self, x, y, t):
        self.clicks.append({"seq": len(self.clicks) + 1, "x": x, "y": y, "t": t})

    def get_clicks(self, after=0):
        self.requests.append(after)
        if self.recording is None:
            return None  # older watchdog without /clicks
        return {
            "recording": self.recording,
            "last_seq": len(self.clicks),
            "clicks": [c for c in self.clicks if c["seq"] > after],
        }


class FakeWebcamHistory:
    """Frames exist for times >= ``since``; each frame's bytes name its time."""

    def __init__(self, since=0.0):
        self.since = since

    def get_frame_at(self, t):
        return f"frame@{t:.1f}".encode() if t >= self.since else None


class FakeVisionCalibration:
    def __init__(self):
        self.points = []

    def add_calibration_point(self, x, y, frames, implicit=False):
        self.points.append((x, y, frames, implicit))
        return {"added": True}


def calibrator(watchdog, mon=None, **kwargs):
    vision = FakeVisionCalibration()
    c = ClickCalibrator(watchdog, FakeWebcamHistory(), vision, mon or monitor(), **kwargs)
    return c, vision


def test_clicks_become_implicit_points_with_frames_from_just_before():
    """Each new click is sent as an implicit calibration point with the frames from just before it.

    Why: people look at what they click, and usually at the target just before clicking.
    Frames from 0.2 s before up to the click show what the user's eyes did while aiming.
    """
    watchdog = FakeWatchdog()
    c, vision = calibrator(watchdog)
    c.start()
    watchdog.click(500, 300, 100.0)

    assert c.process_new_clicks() == 1
    (x, y, frames, implicit), = vision.points
    assert (x, y, implicit) == (500, 300, True)
    assert frames == [b"frame@99.8", b"frame@99.9", b"frame@100.0"]


def test_clicks_from_before_tracking_started_are_ignored():
    """Only clicks made after ``start()`` are used, and each click is used once.

    Why: clicks from an earlier session (other posture, maybe another person) aren't
    evidence about the current one, and re-sending a click would double its weight.
    """
    watchdog = FakeWatchdog()
    watchdog.click(10, 10, 1.0)
    c, vision = calibrator(watchdog)
    c.start()
    watchdog.click(20, 20, 2.0)

    c.process_new_clicks()
    c.process_new_clicks()

    assert [p[:2] for p in vision.points] == [(20, 20)]


def test_click_positions_are_converted_to_the_tracked_area():
    """Absolute desktop clicks are converted to tracked-area coordinates; clicks on other screens are skipped.

    Why: calibration targets and predictions are relative to the tracked monitor (or the
    virtual desktop). Here the tracked monitor sits right of the primary, so (2020, 100)
    is (100, 100), and a click on the primary at (500, 500) is outside the tracked area.
    """
    watchdog = FakeWatchdog()
    c, vision = calibrator(watchdog, mon=monitor(x=1920, y=0))
    c.start()
    watchdog.click(2020, 100, 5.0)
    watchdog.click(500, 500, 5.5)

    c.process_new_clicks()

    assert [p[:2] for p in vision.points] == [(100, 100)]


def test_clicks_in_virtual_desktop_dead_zones_are_skipped():
    """With several monitors, a click inside the bounding box but on no monitor is skipped.

    Why: only real screen positions can be calibration targets.
    """
    left, right = monitor(0, 0, 1920, 1080), monitor(1920, 0, 1920, 1200)
    virtual = SimpleNamespace(x=0, y=0, width=3840, height=1200, monitors=(left, right))
    watchdog = FakeWatchdog()
    c, vision = calibrator(watchdog, mon=virtual)
    c.start()
    watchdog.click(100, 1150, 1.0)  # below the left monitor: dead zone
    watchdog.click(3000, 1150, 1.5)  # on the taller right monitor

    c.process_new_clicks()

    assert [p[:2] for p in vision.points] == [(3000, 1150)]


def test_only_the_newest_clicks_are_used_per_tick():
    """At most ``max_clicks_per_tick`` clicks are sent per tick: the most recent ones.

    Why: each click costs a vision-service request inside the tracking tick, and older
    clicks may already have left the webcam's 5-second frame history.
    """
    watchdog = FakeWatchdog()
    c, vision = calibrator(watchdog, max_clicks_per_tick=2)
    c.start()
    for i in range(5):
        watchdog.click(100 + i, 100, 10.0 + i)

    c.process_new_clicks()

    assert [p[0] for p in vision.points] == [103, 104]


def test_clicks_without_frames_are_skipped():
    """A click with no recorded frame around it isn't sent.

    Why: a point without frames would carry no gaze information.
    """
    watchdog = FakeWatchdog()
    vision = FakeVisionCalibration()
    c = ClickCalibrator(watchdog, FakeWebcamHistory(since=1000.0), vision, monitor())
    c.start()
    watchdog.click(100, 100, 5.0)

    assert c.process_new_clicks() == 0 and vision.points == []


def test_disabled_when_the_watchdog_cannot_record():
    """An older watchdog (no ``/clicks``) or one that can't record turns implicit calibration off.

    Why: tracking must work unchanged with older watchdogs, without polling forever.
    """
    for recording in (None, False):
        watchdog = FakeWatchdog(recording=recording)
        c, vision = calibrator(watchdog)

        assert c.start() is False
        assert c.process_new_clicks() == 0
        assert len(watchdog.requests) == 1

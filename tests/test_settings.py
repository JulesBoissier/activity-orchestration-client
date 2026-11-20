"""Behaviour of ``Settings.from_env``."""

from src.settings import ServiceAddress, Settings


def test_defaults_match_the_services_default_ports():
    """With no variables set, the orchestrator expects every service on localhost at its default port.

    Why: a fresh install works with no configuration.
    """
    s = Settings.from_env({})

    assert (s.vision, s.webcam, s.watchdog) == (
        ServiceAddress("127.0.0.1", 8000),
        ServiceAddress("127.0.0.1", 8001),
        ServiceAddress("127.0.0.1", 8002),
    )
    assert s.period_s == 2.0 and s.monitor_index is None


def test_existing_variable_names_keep_working():
    """The ``*_SERVICE_IP``/``*_SERVICE_PORT`` variables used before keep their meaning.

    Why: existing ``.env`` files and the benchmark replay instructions use them.
    """
    s = Settings.from_env(
        {
            "VISION_TRACKING_SERVICE_PORT": "8100",
            "WINDOWS_WEBCAM_SERVICE_IP": "172.20.0.1",
            "WINDOWS_WEBCAM_SERVICE_PORT": "9001",
            "SYSTEM_WATCHDOG_SERVICE_PORT": "9002",
        }
    )

    assert s.vision == ServiceAddress("127.0.0.1", 8100)
    assert s.webcam == ServiceAddress("172.20.0.1", 9001)
    assert s.watchdog.port == 9002


def test_tracking_options():
    """Tick period, tracked monitor and database location are configurable.

    Why: these used to be constructor defaults scattered across main.py and lifecycle.py.
    An empty TRACKED_MONITOR_INDEX means "all monitors", like leaving it unset.
    """
    s = Settings.from_env(
        {"TRACKING_PERIOD_S": "0.5", "TRACKED_MONITOR_INDEX": "2", "ACTIVITY_DB_URL": "sqlite:///x.db"}
    )

    assert (s.period_s, s.monitor_index, s.activity_db_url) == (0.5, 2, "sqlite:///x.db")
    assert Settings.from_env({"TRACKED_MONITOR_INDEX": " "}).monitor_index is None


def test_frames_per_prediction_defaults_to_a_burst_of_three():
    """Predictions use 3 frames by default; ``FRAMES_PER_PREDICTION`` changes it, never below 1.

    Why: 3 frames measurably improved accuracy on the benchmark; machines too slow to
    finish a 3-frame tick within the period can set 1.
    """
    assert Settings.from_env({}).frames_per_prediction == 3
    assert Settings.from_env({"FRAMES_PER_PREDICTION": "1"}).frames_per_prediction == 1
    assert Settings.from_env({"FRAMES_PER_PREDICTION": "0"}).frames_per_prediction == 1


def test_implicit_calibration_is_off_unless_enabled():
    """Implicit calibration from clicks is off by default and enabled with IMPLICIT_CALIBRATION=1.

    Why: it records clicks and its benefit is unproven on the benchmark so far.
    """
    assert Settings.from_env({}).implicit_calibration is False
    assert Settings.from_env({"IMPLICIT_CALIBRATION": "1"}).implicit_calibration is True

"""Scoring of the interactive accuracy test (``PerformanceMonitoringGUI``)."""

import pytest

from src.backend.accuracy_scoring import score_accuracy_test
from tests.conftest import monitor

MON = monitor(0, 0, 1920, 1080)


def test_perfect_predictions():
    """Predictions on their targets score zero error and full quadrant accuracy.

    Why: anchors the scale of every number the accuracy test prints.
    """
    targets = [(100, 100), (1800, 100), (100, 1000), (1800, 1000)]

    report = score_accuracy_test(targets, targets, MON)

    assert report.rmse_px == 0 and report.median_error_px == 0
    assert report.quadrant_accuracy == 1
    assert report.confusion[0][0] == report.confusion[3][3] == 1


def test_missing_predictions_are_counted_not_crashed_on():
    """Dots where the vision service found no face are counted and left out of the error.

    Why: blinking or glancing at the keyboard during the test is normal. It used to crash
    the report (numpy can't subtract None). "No face" and "wrong place" are different
    failures, the same distinction the benchmark makes.
    """
    report = score_accuracy_test(
        [(100, 100), (500, 500)], [[None, None], (530, 540)], MON
    )

    assert report.no_prediction == 1
    assert report.median_error_px == pytest.approx(50)


def test_predictions_off_the_monitor_are_quadrant_misses():
    """A prediction outside the monitor counts as a miss in its own column, without crashing.

    Why: the interpolation used to keep predictions on screen, but other calibration models
    and multi-monitor setups don't, and a region lookup outside the monitor used to raise.
    """
    report = score_accuracy_test([(100, 100)], [(-50, 100)], MON)

    assert report.off_monitor == 1
    assert report.quadrant_accuracy == 0
    assert report.confusion[0][4] == 1


def test_dot_on_the_last_pixel_belongs_to_the_monitor():
    """A target drawn on the far edge of the monitor is scored in its edge quadrant.

    Why: the GUI picks random dot positions up to the monitor's width and height. A dot on
    that edge used to fall outside every region and crash the report.
    """
    report = score_accuracy_test([(1920, 1080)], [(1900, 1070)], MON)

    assert report.quadrant_accuracy == 1


def test_error_is_euclidean_distance():
    """RMSE is the root mean square of Euclidean pixel errors.

    Why: matches the benchmark's ``error_px.rmse``, so numbers from the interactive test
    and the benchmark are comparable. The old formula averaged x and y errors separately,
    which made it about 1.4x smaller.
    """
    report = score_accuracy_test([(0, 0), (0, 0)], [(30, 40), (60, 80)], MON)

    assert report.rmse_px == pytest.approx(((50**2 + 100**2) / 2) ** 0.5)

"""Scoring for the interactive accuracy test (``PerformanceMonitoringGUI``).

Kept separate from the GUI so it can be tested without a display. The rules match the
attention-benchmark's: a missing prediction (no face) is counted, not scored as an error,
and errors are Euclidean distances in pixels.
"""

from dataclasses import dataclass, field
from math import hypot, sqrt
from typing import List, Optional, Sequence, Tuple

from src.backend.screen_region import MonitorUtility

Point = Tuple[float, float]


@dataclass
class AccuracyReport:
    samples: int
    no_prediction: int
    rmse_px: Optional[float]  # over samples with a prediction
    median_error_px: Optional[float]
    quadrant_accuracy: Optional[float]  # share of predictions in the target's quadrant
    off_monitor: int  # predictions outside the monitor (counted as quadrant misses)
    # confusion[target quadrant][predicted quadrant]; column 4 = off the monitor
    confusion: List[List[int]] = field(default_factory=list)


def _quadrant(monitor, x: float, y: float) -> Optional[int]:
    regions = MonitorUtility.create_screen_region_list(monitor, 2)
    region = MonitorUtility.find_screen_region(x, y, monitor, 2)
    return None if region is None else regions.index(region)


def score_accuracy_test(
    targets: Sequence[Point], predictions: Sequence[Optional[Sequence]], monitor
) -> AccuracyReport:
    """Score predictions against the dots shown, both in the monitor's local coordinates."""
    if len(targets) != len(predictions):
        raise ValueError("one prediction per target is required")

    confusion = [[0] * 5 for _ in range(4)]
    errors: List[float] = []
    no_prediction = off_monitor = hits = 0
    for target, prediction in zip(targets, predictions):
        if prediction is None or prediction[0] is None or prediction[1] is None:
            no_prediction += 1
            continue
        errors.append(hypot(prediction[0] - target[0], prediction[1] - target[1]))
        # Clamp targets onto the monitor: dots drawn on the last pixel row/column belong to it.
        tq = _quadrant(
            monitor,
            min(max(target[0], 0), monitor.width - 1),
            min(max(target[1], 0), monitor.height - 1),
        )
        pq = _quadrant(monitor, prediction[0], prediction[1])
        if pq is None:
            off_monitor += 1
            confusion[tq][4] += 1
        else:
            confusion[tq][pq] += 1
            hits += tq == pq

    errors.sort()
    n = len(errors)
    median = None
    if n:
        median = errors[n // 2] if n % 2 else (errors[n // 2 - 1] + errors[n // 2]) / 2
    return AccuracyReport(
        samples=len(targets),
        no_prediction=no_prediction,
        rmse_px=sqrt(sum(e * e for e in errors) / n) if n else None,
        median_error_px=median,
        quadrant_accuracy=hits / n if n else None,
        off_monitor=off_monitor,
        confusion=confusion,
    )

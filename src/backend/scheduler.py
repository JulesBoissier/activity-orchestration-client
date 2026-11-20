"""Running a job at a fixed rate."""

import logging
import threading
import time
from typing import Callable

log = logging.getLogger(__name__)


def run_every(
    period_s: float,
    job: Callable[[], object],
    stop: threading.Event,
    on_error: Callable[[Exception], None] = lambda exc: log.exception("job failed"),
    clock: Callable[[], float] = time.monotonic,
) -> None:
    """Call ``job()`` every ``period_s`` seconds, start to start, until ``stop`` is set.

    - Sleeps between runs (``stop.wait``), so it uses no CPU while idle and stops promptly.
    - Fixed rate: runs start on a regular grid, however long each run takes. The dashboard
      derives time spent from the spacing between samples, so regular spacing matters.
    - A run that overruns its slot doesn't cause a burst of catch-up runs: missed slots
      are skipped and the next run starts on the next free slot of the grid.
    - An exception from ``job`` goes to ``on_error`` and the schedule continues: one failed
      sample (a service restarting) mustn't end tracking.
    """
    if period_s <= 0:
        raise ValueError("period_s must be positive")
    next_start = clock()
    while not stop.is_set():
        try:
            job()
        except Exception as exc:  # noqa: BLE001 - any failure of one run is survivable
            on_error(exc)
        next_start += period_s
        now = clock()
        if next_start < now:  # overran: skip to the next slot on the grid
            next_start += ((now - next_start) // period_s + 1) * period_s
        stop.wait(next_start - now)

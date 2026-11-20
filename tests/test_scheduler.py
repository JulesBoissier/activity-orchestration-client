"""Behaviour of ``run_every``, the fixed-rate scheduler behind the tracking loop.

Runs on a fake clock: ``FakeStop.wait`` advances time instead of sleeping, so the tests
are instant and exact.
"""

import pytest

from src.backend.scheduler import run_every


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class FakeStop:
    """Duck-types ``threading.Event``: waiting advances the fake clock."""

    def __init__(self, clock):
        self.clock = clock
        self._set = False

    def is_set(self):
        return self._set

    def set(self):
        self._set = True

    def wait(self, timeout):
        assert timeout >= 0
        self.clock.now += timeout


def schedule(period, job_duration, runs, fail_on=()):
    clock = FakeClock()
    stop = FakeStop(clock)
    starts, errors = [], []

    def job():
        starts.append(clock.now)
        clock.now += job_duration
        if len(starts) in fail_on:
            raise RuntimeError(f"run {len(starts)} failed")
        if len(starts) == runs:
            stop.set()

    run_every(period, job, stop, on_error=errors.append, clock=clock)
    return starts, errors


def test_runs_start_on_a_fixed_grid_whatever_they_take():
    """Runs start every ``period`` seconds, start to start, even when each run takes time.

    Why: the dashboard turns the spacing between samples into time spent. The old loop
    restarted its timer after each tick, so samples came every period + tick duration
    (2.4-2.8 s instead of 2 s), varying with how slow the vision service was.
    """
    starts, _ = schedule(period=2.0, job_duration=0.4, runs=4)

    assert starts == pytest.approx([0.0, 2.0, 4.0, 6.0])


def test_an_overrun_is_logged(caplog):
    """A run longer than the period logs a warning with its duration.

    Why: skipped slots silently lower the sampling rate. With bursts of several frames per
    tick, a slow machine can overrun every tick; the warning says which setting to change.
    """
    schedule(period=2.0, job_duration=3.0, runs=2)

    assert "longer than the 2.0 s period" in caplog.text
    assert "FRAMES_PER_PREDICTION" in caplog.text


def test_an_overrun_skips_missed_slots_instead_of_bursting():
    """A run longer than the period delays the next run to the next free slot; no catch-up burst.

    Why: when the vision service stalls, a burst of back-to-back catch-up ticks would
    hammer it as it recovers and record samples milliseconds apart.
    """
    starts, _ = schedule(period=2.0, job_duration=5.0, runs=3)

    assert starts == pytest.approx([0.0, 6.0, 12.0])


def test_a_failing_run_is_reported_and_the_schedule_continues():
    """An exception from one run goes to ``on_error``; the next run happens on time.

    Why: a service restarting makes one tick fail. The old loop let that exception escape
    and ended tracking until someone restarted the orchestrator.
    """
    starts, errors = schedule(period=2.0, job_duration=0.1, runs=3, fail_on={2})

    assert starts == pytest.approx([0.0, 2.0, 4.0])
    assert [str(e) for e in errors] == ["run 2 failed"]


def test_idle_time_is_spent_waiting_not_spinning():
    """Between runs the scheduler waits once for the remaining time, instead of polling.

    Why: the old loop re-checked the clock in a tight loop, keeping a CPU core at 100%
    around the clock.
    """
    clock = FakeClock()
    waits = []

    class CountingStop(FakeStop):
        def wait(self, timeout):
            waits.append(timeout)
            super().wait(timeout)

    stop = CountingStop(clock)
    runs = []

    def job():
        runs.append(clock.now)
        clock.now += 0.5
        if len(runs) == 3:
            stop.set()

    run_every(2.0, job, stop, clock=clock)

    assert waits == pytest.approx([1.5, 1.5, 1.5])


def test_period_must_be_positive():
    """A zero or negative period is refused.

    Why: it would turn the scheduler back into a busy loop.
    """
    with pytest.raises(ValueError):
        run_every(0, lambda: None, FakeStop(FakeClock()))

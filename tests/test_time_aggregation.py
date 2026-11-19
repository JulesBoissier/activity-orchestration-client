"""How the dashboard turns stored samples into time spent per application.

Rows are stored raw, one per tracking tick. Durations are derived when reading: each sample
counts for the gap to its nearest neighbour, capped at 60 seconds. These tests pin that
rule and the period/bucket arithmetic the charts and stats cards share.
"""

from datetime import datetime, timedelta

import pytest

from src.app.chart_builder import build_chart
from src.app.time_aggregation import (
    aggregate_weighted_minutes,
    build_buckets,
    compute_period,
)

MONDAY_9AM = datetime(2026, 11, 16, 9, 0, 0)


def rows(start, count, every_s, app="code.exe"):
    return [
        {"timestamp": (start + timedelta(seconds=i * every_s)).isoformat(), "process_name": app}
        for i in range(count)
    ]


def minutes_by_app(sample_rows, step="hour", start=MONDAY_9AM.replace(hour=0)):
    buckets = build_buckets(step, start, start + timedelta(days=1))
    counts, _ = aggregate_weighted_minutes(sample_rows, step, buckets)
    totals = {}
    for per_app in counts.values():
        for app, minutes in per_app.items():
            totals[app] = totals.get(app, 0.0) + minutes
    return totals


def test_regular_samples_count_their_sampling_interval():
    """With samples every 2 s, each sample counts for 2 s.

    Why: the tracker samples on a fixed period, so N samples should add up to N periods
    whatever the period is. Nothing in the rule hard-codes 2 s.
    """
    totals = minutes_by_app(rows(MONDAY_9AM, 30, every_s=2))

    assert totals["code.exe"] == pytest.approx(30 * 2 / 60)


def test_isolated_sample_counts_at_most_one_minute():
    """A sample with no neighbours (tracker stopped, laptop closed) counts for 60 s.

    Why: without a cap the last sample before a pause would absorb the whole pause. 60 s is
    the maximum time attributed without corroborating samples.
    """
    sample_rows = rows(MONDAY_9AM, 1, every_s=2) + rows(
        MONDAY_9AM + timedelta(hours=3), 1, every_s=2, app="chrome.exe"
    )

    totals = minutes_by_app(sample_rows)

    assert totals == {"code.exe": pytest.approx(1.0), "chrome.exe": pytest.approx(1.0)}


def test_switching_apps_splits_time_between_them():
    """Alternating samples split time between apps in proportion to their sample counts.

    Why: the dashboard's main claim is "how much time went to each app". With regular
    sampling, the share must follow the share of samples.
    """
    a = rows(MONDAY_9AM, 20, every_s=4, app="code.exe")
    b = rows(MONDAY_9AM + timedelta(seconds=2), 10, every_s=8, app="chrome.exe")

    totals = minutes_by_app(a + b)

    assert totals["code.exe"] == pytest.approx(2 * totals["chrome.exe"], rel=0.05)


@pytest.mark.parametrize("empty", ["", None, "   "])
def test_samples_without_a_window_are_not_counted(empty):
    """Gap rows (no PoR, or PoR on no window) don't count as time for any app.

    Why: a gap means the tracker couldn't tell what the user was looking at. Crediting it
    to an app would inflate that app's total.
    """
    sample_rows = rows(MONDAY_9AM, 10, every_s=2) + [
        {"timestamp": (MONDAY_9AM + timedelta(minutes=5)).isoformat(), "process_name": empty}
    ]

    totals = minutes_by_app(sample_rows)

    assert set(totals) == {"code.exe"}


def test_gap_rows_bound_the_previous_sample():
    """A sample followed 2 s later by a gap row counts for 2 s, not the 60 s isolated maximum.

    Why: the tracker writes gap rows so the timeline shows when tracking ran without a
    result. Their timestamps are the evidence that attention to the previous app ended;
    ignoring them credits up to a minute of "looking away" to the last app seen.
    """
    sample_rows = [
        {"timestamp": MONDAY_9AM.isoformat(), "process_name": "code.exe"},
        {"timestamp": (MONDAY_9AM + timedelta(seconds=2)).isoformat(), "process_name": ""},
    ]

    assert minutes_by_app(sample_rows)["code.exe"] == pytest.approx(2 / 60)


def test_samples_land_in_the_bucket_of_their_timestamp():
    """With hourly buckets, samples at 09:30 and 10:30 are counted in different hours.

    Why: the stacked bar chart shows when attention went where, not only how much.
    """
    start = MONDAY_9AM.replace(hour=0)
    sample_rows = rows(MONDAY_9AM + timedelta(minutes=30), 1, 2) + rows(
        MONDAY_9AM + timedelta(minutes=90), 1, 2, app="chrome.exe"
    )
    buckets = build_buckets("hour", start, start + timedelta(days=1))

    counts, _ = aggregate_weighted_minutes(sample_rows, "hour", buckets)

    assert dict(counts[MONDAY_9AM]) == {"code.exe": pytest.approx(1.0)}
    assert dict(counts[MONDAY_9AM + timedelta(hours=1)]) == {"chrome.exe": pytest.approx(1.0)}


@pytest.mark.parametrize(
    "period,expected_start,step",
    [
        ("today", datetime(2026, 11, 19, 0, 0), "hour"),
        ("week", datetime(2026, 11, 16, 0, 0), "day"),  # Monday
        ("month", datetime(2026, 11, 1, 0, 0), "week"),
        ("year", datetime(2026, 1, 1, 0, 0), "month"),
    ],
)
def test_periods_start_at_calendar_boundaries(period, expected_start, step):
    """Each dashboard period runs from the start of the current day/week/month/year until now.

    Why: users read "This Week" as calendar week (ISO, starting Monday), not "last 7 days".
    The bucket size grows with the period so charts keep a readable number of bars.
    """
    now = datetime(2026, 11, 19, 15, 42)

    start, end, got_step = compute_period(now, period)

    assert (start, end, got_step) == (expected_start, now, step)


def test_two_percent_threshold_hides_minor_apps():
    """With the 2% threshold on, apps under 2% of the period's total are left out of the chart.

    Why: dozens of briefly glanced-at apps otherwise drown the legend. The threshold is
    relative so it works the same for a day and a year.
    """
    end = datetime.now() - timedelta(seconds=5)
    major = rows(end - timedelta(seconds=200), 100, every_s=2, app="code.exe")  # ~200 s
    minor = [  # 3 s after the last major sample, so ~1.5% of the total
        {"timestamp": (end + timedelta(seconds=1)).isoformat(), "process_name": "calc.exe"}
    ]

    shown = {t.name for t in build_chart(major + minor, "year", 0.02).data}
    shown_all = {t.name for t in build_chart(major + minor, "year", 0.0).data}

    assert shown == {"code.exe"}
    assert shown_all == {"code.exe", "calc.exe"}

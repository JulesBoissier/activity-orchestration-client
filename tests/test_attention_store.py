"""Behaviour of ``AttentionTrackerStore``, the SQLite table shared by tracker and dashboard."""

import os
import sys
import time
from datetime import datetime, timedelta

import pytest

from src.backend.attention_tracker_store import AttentionTracker, AttentionTrackerStore
from tests.conftest import stored_rows


def test_saved_samples_are_readable_by_another_connection(tmp_path):
    """A sample written by the tracker is visible to a separate store on the same file.

    Why: the tracker and the Dash app are separate processes. The SQLite file is their only
    link.
    """
    url = f"sqlite:///{tmp_path / 'attention.db'}"
    AttentionTrackerStore(url).save_attention(process_name="code.exe", window_title="main.py")

    assert stored_rows(AttentionTrackerStore(url)) == [("code.exe", "main.py")]


@pytest.fixture
def far_from_utc_timezone():
    if not hasattr(time, "tzset"):
        pytest.skip("time.tzset is unavailable on this platform")
    old = os.environ.get("TZ")
    os.environ["TZ"] = "Asia/Tokyo"  # UTC+9, no DST
    time.tzset()
    yield
    if old is None:
        os.environ.pop("TZ")
    else:
        os.environ["TZ"] = old
    time.tzset()


@pytest.mark.skipif(sys.platform == "win32", reason="needs time.tzset")
@pytest.mark.xfail(
    strict=True,
    reason="Known bug: timestamps default to SQLite CURRENT_TIMESTAMP (UTC) while the dashboard "
    "filters with local datetime.now().",
)
def test_sample_timestamp_matches_dashboard_clock(tracker_store, far_from_utc_timezone):
    """A sample's stored timestamp is within a few seconds of the dashboard's ``datetime.now()``.

    Why: the dashboard compares stored timestamps with ``datetime.now()`` to decide what
    falls in "Today" or "This Week". Both must use the same clock, or every period
    boundary shifts by the UTC offset.
    """
    tracker_store.save_attention(process_name="code.exe", window_title="main.py")

    session = tracker_store.Session()
    stored = session.query(AttentionTracker).one().timestamp
    session.close()

    assert abs(stored - datetime.now()) < timedelta(seconds=5)

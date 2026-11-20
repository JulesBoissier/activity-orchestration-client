"""Behaviour of ``AttentionTrackerStore``, the SQLite table shared by tracker and dashboard."""

import os
import sqlite3
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


def _old_database(path, utc_timestamps):
    """A database as the previous version wrote it: SQLite CURRENT_TIMESTAMP (UTC) text."""
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE attention_tracker (id INTEGER PRIMARY KEY, timestamp DATETIME, "
        "process_name VARCHAR, window_title VARCHAR)"
    )
    con.executemany(
        "INSERT INTO attention_tracker (timestamp, process_name, window_title) VALUES (?, ?, ?)",
        [(ts, "code.exe", "main.py") for ts in utc_timestamps],
    )
    con.commit()
    con.close()


def _timestamps(store):
    session = store.Session()
    try:
        return [r.timestamp for r in session.query(AttentionTracker).order_by(AttentionTracker.id)]
    finally:
        session.close()


@pytest.mark.skipif(sys.platform == "win32", reason="needs time.tzset")
def test_existing_utc_history_is_converted_to_local_time_once(tmp_path, far_from_utc_timezone):
    """Rows written by the previous version (UTC) are moved to local time, exactly once.

    Why: switching new rows to local time alone would leave months of history hours away
    from today's rows, misplacing it in every chart. The conversion is recorded in SQLite's
    user_version, so opening the database again (the tracker and the dashboard both do)
    never shifts it twice.
    """
    path = tmp_path / "attention.db"
    _old_database(path, ["2026-11-19 08:00:00", "2026-11-19 23:30:15"])  # UTC
    url = f"sqlite:///{path}"

    first = _timestamps(AttentionTrackerStore(url))
    second = _timestamps(AttentionTrackerStore(url))

    # Asia/Tokyo is UTC+9.
    assert first == [datetime(2026, 11, 19, 17, 0, 0), datetime(2026, 11, 20, 8, 30, 15)]
    assert second == first


@pytest.mark.skipif(sys.platform == "win32", reason="needs time.tzset")
def test_new_database_is_not_converted(tmp_path, far_from_utc_timezone):
    """A database created by this version is never treated as UTC history.

    Why: its rows are already in local time; converting them would shift them by the UTC
    offset.
    """
    url = f"sqlite:///{tmp_path / 'attention.db'}"
    store = AttentionTrackerStore(url)
    store.save_attention(process_name="code.exe", window_title="main.py")
    before = _timestamps(store)

    assert _timestamps(AttentionTrackerStore(url)) == before

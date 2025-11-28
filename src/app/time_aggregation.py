from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

from src.app.period_iterators import PeriodIterators


def to_dt(ts) -> Optional[datetime]:
    if isinstance(ts, datetime):
        return ts
    try:
        return datetime.fromisoformat(str(ts))
    except Exception:
        return None


def compute_period(now: datetime, period_value: str) -> Tuple[datetime, datetime, str]:
    """Return (start, end, step) for a given named period."""
    if period_value == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now
        step = "hour"
    elif period_value == "week":
        start = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end = now
        step = "day"
    elif period_value == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = now
        step = "week"
    else:  # "year"
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end = now
        step = "month"
    return start, end, step


def build_buckets(step: str, start: datetime, end: datetime) -> List[datetime]:
    if step == "month":
        return list(PeriodIterators.month_iter(start, end))
    if step == "week":
        return list(PeriodIterators.week_iter(start, end))
    if step == "day":
        return list(PeriodIterators.day_iter(start, end))
    return list(PeriodIterators.hour_iter(start, end))


def normalize_events(rows: List) -> List[Tuple[datetime, str]]:
    """Turn ORM/dict rows into sorted (timestamp, category) pairs."""
    events: List[Tuple[datetime, str]] = []
    for r in rows:
        ts = (
            getattr(r, "timestamp", None)
            if not isinstance(r, dict)
            else r.get("timestamp")
        )
        dt = to_dt(ts)
        if not dt:
            continue
        if isinstance(r, dict):
            cat = r.get("process_name") or r.get("viewed_window_info") or "Unknown"
        else:
            cat = (
                getattr(r, "process_name", None)
                or getattr(r, "viewed_window_info", None)
                or "Unknown"
            )
        # Skip empty or unknown categories; do not include events without a process name
        cat_str = str(cat).strip() if cat is not None else ""
        if not cat_str or cat_str.lower() == "unknown":
            continue
        events.append((dt, cat_str))
    events.sort(key=lambda t: t[0])
    return events


def compute_event_duration_seconds(
    events: List[Tuple[datetime, str]], index: int
) -> float:
    """Duration for one event as min distance to neighbors; standalone counts as 60s."""
    prev_dt = events[index - 1][0] if index > 0 else None
    next_dt = events[index + 1][0] if index < len(events) - 1 else None
    deltas = [60.0]
    if prev_dt:
        deltas.append((events[index][0] - prev_dt).total_seconds())
    if next_dt:
        deltas.append((next_dt - events[index][0]).total_seconds())
    return min(deltas)


def snap_to_bucket(dt: datetime, step: str) -> datetime:
    """Return the bucket-aligned timestamp for a given dt and step."""
    if step == "month":
        return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if step == "week":
        return (dt - timedelta(days=dt.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    if step == "day":
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return dt.replace(minute=0, second=0, microsecond=0)


def aggregate_weighted_minutes(
    rows: List, step: str, buckets: List[datetime]
) -> Tuple[Dict[datetime, Dict[str, float]], Set[str]]:
    """Aggregate durations per bucket per category in minutes.
    Each event contributes min(distance to previous, distance to next). Singletons count as 60s.
    """
    events = normalize_events(rows)
    counts: Dict[datetime, Dict[str, float]] = {b: defaultdict(float) for b in buckets}
    categories: Set[str] = set(cat for _, cat in events)

    for i, (dt, cat) in enumerate(events):
        dur_s = compute_event_duration_seconds(events, i)
        if dur_s <= 0:
            continue
        snap = snap_to_bucket(dt, step)
        if snap not in counts:
            continue
        counts[snap][cat] += dur_s / 60.0

    return counts, categories

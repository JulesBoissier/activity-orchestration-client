from datetime import datetime
from typing import Any, Dict, List

from dash import html

from src.app.time_aggregation import (
    aggregate_weighted_minutes,
    build_buckets,
    compute_period,
)


def build_stats_cards(
    data: List[Dict[str, Any]] | None,
    period_value: str,
    apply_min_threshold: float = 0.0,
):
    """Builds Dash HTML stat cards for the given data and selected period."""
    now = datetime.now()
    start, end, step = compute_period(now, period_value)

    rows = data or []

    def _parse_ts(item):
        try:
            return datetime.fromisoformat(str(item.get("timestamp")))
        except Exception:
            return None

    rows = [r for r in rows if (ts := _parse_ts(r)) is not None and start <= ts <= end]

    buckets = build_buckets(step, start, end)
    counts, _categories = aggregate_weighted_minutes(rows, step, buckets)

    totals_by_app: Dict[str, float] = {}
    for b in buckets:
        for app_name, minutes in counts.get(b, {}).items():
            totals_by_app[app_name] = totals_by_app.get(app_name, 0.0) + minutes

    # Apply percentage threshold of total time if requested
    total_all = sum(totals_by_app.values())
    threshold = (apply_min_threshold or 0.0) * total_all if total_all > 0 else 0.0
    included = {
        app: total for app, total in totals_by_app.items() if total >= threshold
    }

    total_minutes = sum(included.values())
    most_viewed = max(included.items(), key=lambda kv: kv[1])[0] if included else "—"
    most_viewed_minutes = included.get(most_viewed, 0.0) if included else 0.0
    distinct_apps = len([a for a in included.keys() if a and a != "Unknown"])

    def fmt_minutes(m: float) -> str:
        h = int(m // 60)
        mi = int(round(m % 60))
        if h > 0:
            return f"{h}h {mi}m"
        return f"{mi}m"

    card_style = {
        "border": "1px solid #e2e2e2",
        "borderRadius": "6px",
        "padding": "10px 12px",
        "minWidth": "180px",
        "background": "#fafafa",
        "boxShadow": "0 1px 3px rgba(0,0,0,0.08)",
    }

    return [
        html.Div(
            [
                html.Div("Total Time", style={"fontWeight": "600"}),
                html.Div(fmt_minutes(total_minutes), style={"fontSize": "20px"}),
            ],
            style=card_style,
        ),
        html.Div(
            [
                html.Div("Most Viewed App", style={"fontWeight": "600"}),
                html.Div(most_viewed),
                html.Div(fmt_minutes(most_viewed_minutes), style={"color": "#666"}),
            ],
            style=card_style,
        ),
        html.Div(
            [
                html.Div("Distinct Apps", style={"fontWeight": "600"}),
                html.Div(str(distinct_apps), style={"fontSize": "20px"}),
            ],
            style=card_style,
        ),
    ]

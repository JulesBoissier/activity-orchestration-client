from datetime import datetime
from typing import Any, Dict, List

import plotly.graph_objects as go

from src.app.time_aggregation import (
    aggregate_weighted_minutes,
    build_buckets,
    compute_period,
)


def _parse_ts(item: Dict[str, Any]) -> datetime | None:
    try:
        return datetime.fromisoformat(str(item.get("timestamp")))
    except Exception:
        return None


def build_chart(data: List[Dict[str, Any]] | None, period_value: str) -> go.Figure:
    """Build the stacked bar chart filtered by the selected period."""
    now = datetime.now()
    start, end, step = compute_period(now, period_value)

    rows = data or []
    rows = [r for r in rows if (ts := _parse_ts(r)) is not None and start <= ts <= end]

    buckets = build_buckets(step, start, end)
    counts, categories = aggregate_weighted_minutes(rows, step, buckets)

    traces: List[go.Bar] = []
    for cat in sorted(categories):
        y_vals = [counts[b].get(cat, 0.0) for b in buckets]
        traces.append(
            go.Bar(
                name=cat,
                x=buckets,
                y=y_vals,
                hovertemplate=f"{cat}<br>Minutes=%{{y:.1f}}<extra></extra>",
            )
        )

    fig = go.Figure(
        data=traces,
        layout=go.Layout(
            barmode="stack",
            margin=dict(l=40, r=140, t=20, b=40),
            xaxis_title="Time",
            yaxis_title="Minutes",
        ),
    )
    fig.update_layout(
        template="plotly_white",
        font=dict(size=13),
        uirevision="attention-graph",
        xaxis=dict(type="date"),
        legend=dict(orientation="v", y=1, yanchor="top", x=1.02, xanchor="left"),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#eee")
    fig.update_yaxes(showgrid=True, gridcolor="#eee")

    return fig

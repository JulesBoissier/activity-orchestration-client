from collections import defaultdict
from datetime import datetime, timedelta

import dash_ag_grid as dag
import plotly.graph_objects as go
from dash import Dash, Input, Output, callback, dcc, html

from src.app.time_aggregation import (
    aggregate_weighted_minutes,
    build_buckets,
    compute_period,
)
from src.backend.attention_tracker_store import AttentionTracker, AttentionTrackerStore


def create_app() -> Dash:
    store = AttentionTrackerStore()

    app = Dash(__name__)
    app.title = "Attention Tracker"

    app.layout = html.Div(
        [
            html.H1("Attention Tracker"),
            dcc.Interval(id="refresh", interval=1_000, n_intervals=0),
            dcc.Store(id="attention-data"),
            html.H2("Distribution Over Time"),
            html.Div(
                [
                    html.Label("Period"),
                    dcc.Dropdown(
                        id="period-select",
                        options=[
                            {"label": "Today", "value": "today"},
                            {"label": "This Week", "value": "week"},
                            {"label": "This Month", "value": "month"},
                            {"label": "This Year", "value": "year"},
                        ],
                        value="week",
                        clearable=False,
                        style={"width": "240px"},
                    ),
                ],
                style={"marginBottom": "8px"},
            ),
            dcc.Graph(id="attention-graph"),
            html.Div(
                [
                    html.H2("Recent Entries"),
                    dag.AgGrid(
                        id="attention-grid",
                        columnDefs=[
                            {"headerName": "ID", "field": "id", "maxWidth": 100},
                            {"headerName": "Timestamp", "field": "timestamp"},
                            {"headerName": "Process Name", "field": "process_name"},
                            {"headerName": "Window Title", "field": "window_title"},
                        ],
                        rowData=[],
                        defaultColDef={
                            "resizable": True,
                            "sortable": True,
                            "filter": True,
                            "floatingFilter": True,
                        },
                        dashGridOptions={
                            "rowHeight": 28,
                            "animateRows": False,
                            "domLayout": "autoHeight",
                        },
                        style={"width": "100%"},
                    ),
                ]
            ),
        ],
        style={"maxWidth": "1100px", "margin": "0 auto", "padding": "16px"},
    )

    @callback(
        Output("attention-data", "data"),
        Input("refresh", "n_intervals"),
    )
    def load_data(_):
        session = store.Session()
        try:
            rows = (
                session.query(AttentionTracker)
                .order_by(AttentionTracker.timestamp.desc())
                .all()
            )
            data = [
                {
                    "id": r.id,
                    "timestamp": r.timestamp.isoformat()
                    if isinstance(r.timestamp, datetime)
                    else str(r.timestamp),
                    "process_name": getattr(r, "process_name", None),
                    "window_title": getattr(r, "window_title", None),
                }
                for r in rows
            ]
        finally:
            session.close()
        return data

    @callback(
        Output("attention-graph", "figure"),
        Input("attention-data", "data"),
        Input("period-select", "value"),
    )
    def refresh_chart(data, period_value):
        now = datetime.now()
        # Determine start/end and bucket step based on selected period
        start, end, step = compute_period(now, period_value)

        rows = data or []

        # Filter rows to selected period to avoid cross-period duration bleed
        def _parse_ts(item):
            try:
                return datetime.fromisoformat(str(item.get("timestamp")))
            except Exception:
                return None

        rows = [
            r for r in rows if (ts := _parse_ts(r)) is not None and start <= ts <= end
        ]

        # Build bucket list per step
        buckets = build_buckets(step, start, end)

        # Aggregate weighted durations per bucket per category (minutes)
        counts, categories = aggregate_weighted_minutes(rows, step, buckets)

        # Build stacked bar series for each category
        traces = []
        for cat in sorted(categories):
            y_vals = [counts[b].get(cat, 0.0) for b in buckets]
            # Use datetime buckets on x so Plotly range tools work
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
        # Preserve zoom across refreshes; no external range selector
        fig.update_layout(
            uirevision="attention-graph",
            xaxis=dict(type="date"),
            legend=dict(orientation="v", y=1, yanchor="top", x=1.02, xanchor="left"),
        )

        return fig

    @callback(
        Output("attention-grid", "rowData"),
        Input("attention-data", "data"),
    )
    def refresh_grid(data):
        return data or []

    return app


app = create_app()

server = app.server


if __name__ == "__main__":
    app.run(debug=True)

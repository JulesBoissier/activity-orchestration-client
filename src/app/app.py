from collections import defaultdict
from datetime import datetime, timedelta

import dash_ag_grid as dag
import plotly.graph_objects as go
from dash import Dash, Input, Output, dcc, html

from src.backend.attention_tracker_store import AttentionTracker, AttentionTrackerStore


def create_app() -> Dash:
    store = AttentionTrackerStore()

    app = Dash(__name__)
    app.title = "Attention Tracker"

    app.layout = html.Div(
        [
            html.H1("Attention Tracker"),
            dcc.Interval(id="refresh", interval=5_000, n_intervals=0),
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
                            {
                                "headerName": "Viewed Window",
                                "field": "viewed_window_info",
                            },
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

    @app.callback(
        Output("attention-grid", "rowData"),
        Output("attention-graph", "figure"),
        Input("refresh", "n_intervals"),
        Input("period-select", "value"),
    )
    def refresh_data(_, period_value):
        now = datetime.now()
        # Determine start/end and bucket step based on selected period
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
            start = now.replace(
                month=1, day=1, hour=0, minute=0, second=0, microsecond=0
            )
            end = now
            step = "month"

        # Read latest data
        session = store.Session()
        try:
            rows = (
                session.query(AttentionTracker)
                .filter(AttentionTracker.timestamp >= start)
                .filter(AttentionTracker.timestamp <= end)
                .order_by(AttentionTracker.timestamp.desc())
                .all()
            )
        finally:
            session.close()

        # Prepare table data
        table_data = [
            {
                "id": r.id,
                "timestamp": r.timestamp.isoformat()
                if isinstance(r.timestamp, datetime)
                else str(r.timestamp),
                "viewed_window_info": r.viewed_window_info,
            }
            for r in rows
        ]

        # Helpers for bucketing and labels
        def to_dt(ts):
            if isinstance(ts, datetime):
                return ts
            try:
                return datetime.fromisoformat(str(ts))
            except Exception:
                return None

        def month_iter(start_dt: datetime, end_dt: datetime):
            cur = start_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            while cur <= end_dt:
                yield cur
                year = cur.year + (1 if cur.month == 12 else 0)
                month = 1 if cur.month == 12 else cur.month + 1
                cur = cur.replace(year=year, month=month)

        def week_iter(start_dt: datetime, end_dt: datetime):
            cur = (start_dt - timedelta(days=start_dt.weekday())).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            while cur <= end_dt:
                yield cur
                cur = cur + timedelta(weeks=1)

        def day_iter(start_dt: datetime, end_dt: datetime):
            cur = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            while cur <= end_dt:
                yield cur
                cur = cur + timedelta(days=1)

        def hour_iter(start_dt: datetime, end_dt: datetime):
            cur = start_dt.replace(minute=0, second=0, microsecond=0)
            while cur <= end_dt:
                yield cur
                cur = cur + timedelta(hours=1)

        # Build bucket list per step
        if step == "month":
            buckets = list(month_iter(start, end))
        elif step == "week":
            buckets = list(week_iter(start, end))
        elif step == "day":
            buckets = list(day_iter(start, end))
        else:
            buckets = list(hour_iter(start, end))

        # Aggregate counts per bucket per category (viewed_window_info)
        counts = {b: defaultdict(int) for b in buckets}
        categories = set()
        for r in rows:
            dt = to_dt(r.timestamp)
            if not dt:
                continue
            # snap to bucket start
            if step == "month":
                snap = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            elif step == "week":
                snap = (dt - timedelta(days=dt.weekday())).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
            elif step == "day":
                snap = dt.replace(hour=0, minute=0, second=0, microsecond=0)
            else:
                snap = dt.replace(minute=0, second=0, microsecond=0)
            if snap not in counts:
                # outside generated buckets (race with now) -> skip
                continue
            cat = r.viewed_window_info
            categories.add(cat)
            counts[snap][cat] += 1

        # Build stacked bar series for each category
        traces = []
        for cat in sorted(categories):
            y_vals = [counts[b].get(cat, 0) for b in buckets]
            # Use datetime buckets on x so Plotly range tools work
            traces.append(
                go.Bar(
                    name=cat,
                    x=buckets,
                    y=y_vals,
                    hovertemplate=f"{cat}<br>Count=%{{y}}<extra></extra>",
                )
            )

        fig = go.Figure(
            data=traces,
            layout=go.Layout(
                barmode="stack",
                margin=dict(l=40, r=140, t=20, b=40),
                xaxis_title="Time",
                yaxis_title="Entries",
            ),
        )
        # Preserve zoom across refreshes; no external range selector
        fig.update_layout(
            uirevision="attention-graph",
            xaxis=dict(type="date"),
            legend=dict(orientation="v", y=1, yanchor="top", x=1.02, xanchor="left"),
        )

        return table_data, fig

    return app


app = create_app()

server = app.server


if __name__ == "__main__":
    app.run(debug=True)

from collections import defaultdict
from datetime import datetime

import plotly.graph_objects as go
from dash import Dash, Input, Output, dash_table, dcc, html

from src.backend.attention_tracker_store import AttentionTracker, AttentionTrackerStore


def create_app() -> Dash:
    store = AttentionTrackerStore()

    app = Dash(__name__)
    app.title = "Attention Tracker"

    app.layout = html.Div(
        [
            html.H1("Attention Tracker"),
            dcc.Interval(id="refresh", interval=2_000, n_intervals=0),
            html.Div(
                [
                    html.H2("Recent Entries"),
                    dash_table.DataTable(
                        id="attention-table",
                        columns=[
                            {"name": "id", "id": "id"},
                            {"name": "timestamp", "id": "timestamp"},
                            {"name": "viewed_window_info", "id": "viewed_window_info"},
                        ],
                        data=[],
                        page_size=10,
                        sort_action="native",
                        filter_action="native",
                        style_table={"overflowX": "auto"},
                        style_cell={"textAlign": "left", "padding": "6px"},
                    ),
                ]
            ),
            html.H2("Distribution Over Time"),
            dcc.Graph(id="attention-graph"),
        ],
        style={"maxWidth": "1100px", "margin": "0 auto", "padding": "16px"},
    )

    @app.callback(
        Output("attention-table", "data"),
        Output("attention-graph", "figure"),
        Input("refresh", "n_intervals"),
    )
    def refresh_data(_):
        # Read latest data
        session = store.Session()
        try:
            rows = (
                session.query(AttentionTracker)
                .order_by(AttentionTracker.timestamp.desc())
                .limit(500)
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

        # Aggregate counts by minute
        counts_by_minute = defaultdict(int)
        for r in rows:
            ts = r.timestamp
            if isinstance(ts, datetime):
                bucket = ts.replace(second=0, microsecond=0)
            else:
                # Fallback parse if needed
                try:
                    parsed = datetime.fromisoformat(str(ts))
                    bucket = parsed.replace(second=0, microsecond=0)
                except Exception:
                    continue
            counts_by_minute[bucket] += 1

        # Sort buckets chronologically ascending for a nicer chart
        x_vals = sorted(counts_by_minute.keys())
        y_vals = [counts_by_minute[k] for k in x_vals]

        fig = go.Figure(
            data=[go.Bar(x=x_vals, y=y_vals, marker_color="#636EFA")],
            layout=go.Layout(
                margin=dict(l=40, r=20, t=20, b=40),
                xaxis_title="Time (by minute)",
                yaxis_title="Entries",
            ),
        )

        return table_data, fig

    return app


app = create_app()

server = app.server


if __name__ == "__main__":
    app.run(debug=True)

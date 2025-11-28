from collections import defaultdict
from datetime import datetime, timedelta

import dash_ag_grid as dag
import plotly.graph_objects as go
from dash import Dash, Input, Output, callback, dcc, html

from src.app.chart_builder import build_chart
from src.app.stats_cards import build_stats_cards
from src.app.time_aggregation import compute_period
from src.backend.attention_tracker_store import AttentionTracker, AttentionTrackerStore


def create_app() -> Dash:
    store = AttentionTrackerStore()

    app = Dash(__name__)
    app.title = "Attention Tracker"

    app.layout = html.Div(
        [
            html.Div(
                [
                    html.H1("Attention Tracker", style={"margin": 0}),
                    html.Div(
                        [
                            html.Label("Period", style={"marginRight": "8px"}),
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
                                style={"width": "220px"},
                            ),
                        ],
                        style={"display": "flex", "alignItems": "center", "gap": "8px"},
                    ),
                    html.Div(
                        [
                            dcc.Checklist(
                                id="threshold-2pct",
                                options=[{"label": "2% threshold", "value": "on"}],
                                value=[],
                                inputStyle={"marginRight": "6px"},
                                labelStyle={
                                    "display": "inline-flex",
                                    "alignItems": "center",
                                },
                                style={"marginTop": "2px"},
                            ),
                        ],
                        style={"display": "flex", "alignItems": "center"},
                    ),
                ],
                style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "center",
                    "marginBottom": "10px",
                },
            ),
            dcc.Interval(id="refresh", interval=1_000, n_intervals=0),
            dcc.Store(id="attention-data"),
            html.H2("Distribution Over Time", style={"marginTop": "6px"}),
            html.Div(
                id="stats-cards",
                style={
                    "display": "flex",
                    "gap": "12px",
                    "flexWrap": "wrap",
                    "justifyContent": "center",
                    "marginBottom": "8px",
                },
            ),
            html.Div(
                dcc.Graph(id="attention-graph"),
                style={
                    "background": "#fff",
                    "border": "1px solid #eee",
                    "borderRadius": "8px",
                    "padding": "8px",
                },
            ),
            html.Div(
                [
                    html.H2("Recent Entries"),
                    html.Div(
                        dag.AgGrid(
                            id="attention-grid",
                            columnDefs=[
                                {
                                    "headerName": "Timestamp",
                                    "field": "timestamp",
                                    "width": 250,
                                    "suppressSizeToFit": True,
                                },
                                {
                                    "headerName": "Process Name",
                                    "field": "process_name",
                                    "width": 250,
                                    "suppressSizeToFit": True,
                                },
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
                            columnSize="sizeToFit",
                            style={"width": "100%"},
                        ),
                        style={
                            "background": "#fff",
                            "border": "1px solid #eee",
                            "borderRadius": "8px",
                            "padding": "8px",
                        },
                    ),
                ]
            ),
        ],
        style={
            "maxWidth": "1100px",
            "margin": "0 auto",
            "padding": "16px",
            "background": "#f7f7fb",
        },
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
        Input("threshold-2pct", "value"),
    )
    def refresh_chart(data, period_value, threshold_values):
        apply_pct = bool(threshold_values and "on" in threshold_values)
        pct = 0.02 if apply_pct else 0.0
        return build_chart(data, period_value, apply_min_threshold=pct)

    @callback(
        Output("stats-cards", "children"),
        Input("attention-data", "data"),
        Input("period-select", "value"),
        Input("threshold-2pct", "value"),
    )
    def refresh_stats(data, period_value, threshold_values):
        apply_pct = bool(threshold_values and "on" in threshold_values)
        pct = 0.02 if apply_pct else 0.0
        return build_stats_cards(data, period_value, apply_min_threshold=pct)

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

from __future__ import annotations

from datetime import date, timedelta

import plotly.graph_objects as go

from app import theme
from app.db import get_session
from app.services import forecast, networth


def net_worth_figure(*, height: int = 140, months: int = 6) -> go.Figure:
    with get_session() as session:
        points = networth.trend(session, months=months)
    t = theme.current()

    x = [p[0] for p in points]
    y = [p[1] / 100 for p in points]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x,
            y=y,
            mode="lines+markers",
            line=dict(color=t["accent"], width=2),
            marker=dict(size=5, color=t["accent"]),
            fill="tozeroy",
            fillcolor=theme.rgba(t["accent"], 0.15),
            hovertemplate="%{x}: R$ %{y:,.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, color=t["textm"], type="category"),
        yaxis=dict(showgrid=True, gridcolor=t["border"], color=t["textm"], zeroline=False),
        showlegend=False,
        font=dict(size=11),
    )
    return fig


def forecast_figure(*, height: int = 200, horizon_days: int = 90) -> go.Figure:
    with get_session() as session:
        series = forecast.project_net_worth(session, horizon_days=horizon_days)
    t = theme.current()
    today = date.today()

    x = [p[0] for p in series]
    y = [p[1] / 100 for p in series]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x,
            y=y,
            mode="lines+markers",
            line=dict(color=t["accent2"], width=2, dash="dot"),
            marker=dict(size=5, color=t["accent2"]),
            hovertemplate="%{x|%d/%m}: R$ %{y:,.2f}<extra></extra>",
        )
    )
    fig.add_vline(x=today.isoformat(), line_width=1, line_dash="dash", line_color=t["textm"])
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            showgrid=False,
            color=t["textm"],
            type="date",
            range=[today.isoformat(), (today + timedelta(days=horizon_days)).isoformat()],
        ),
        yaxis=dict(showgrid=True, gridcolor=t["border"], color=t["textm"], zeroline=False),
        showlegend=False,
        font=dict(size=11),
    )
    return fig

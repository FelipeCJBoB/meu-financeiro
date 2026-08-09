from __future__ import annotations

from datetime import date, timedelta

import plotly.graph_objects as go

from app import theme
from app.db import get_session
from app.services import budgets as budgets_service
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


def budget_comparison_figure(month: str, cycle_start_day: int = 1) -> go.Figure:
    """Grouped horizontal bar: orcado vs. gasto per category, worst offenders on top."""
    with get_session() as session:
        rows = budgets_service.budget_progress(session, month, cycle_start_day)
    t = theme.current()
    rows = list(reversed(rows))

    names = [r["category"].name for r in rows]
    budget_vals = [r["budget_cents"] / 100 for r in rows]
    spent_vals = [r["spent_cents"] / 100 for r in rows]
    colors = [
        t["red"] if r["pct"] > 1 else (t["amber"] if r["pct"] >= 0.8 else t["accent"])
        for r in rows
    ]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=names,
            x=budget_vals,
            name="Orcado",
            orientation="h",
            marker=dict(color=theme.rgba(t["textm"], 0.25)),
            hovertemplate="%{y} · orcado: R$ %{x:,.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            y=names,
            x=spent_vals,
            name="Gasto",
            orientation="h",
            marker=dict(color=colors),
            hovertemplate="%{y} · gasto: R$ %{x:,.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        barmode="group",
        margin=dict(l=0, r=0, t=28, b=0),
        height=max(160, len(rows) * 46 + 40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=True, gridcolor=t["border"], color=t["textm"], zeroline=False),
        yaxis=dict(showgrid=False, color=t["text"]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(size=11, color=t["text2"])),
        font=dict(size=11),
    )
    return fig


def composition_donut_figure(*, height: int = 220) -> go.Figure:
    with get_session() as session:
        rows = networth.composition(session)
    t = theme.current()
    rows = [r for r in rows if r["balance_cents"] > 0]

    labels = [r["account"].name for r in rows]
    values = [r["balance_cents"] / 100 for r in rows]
    palette = [t["accent"], t["accent2"], t["amber"], t["green"], t["red"], t["textm"]]
    colors = [palette[i % len(palette)] for i in range(len(rows))]

    fig = go.Figure()
    fig.add_trace(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.6,
            marker=dict(colors=colors, line=dict(color=t["s1"], width=2)),
            textinfo="percent",
            textfont=dict(color="#ffffff", size=11),
            hovertemplate="%{label}: R$ %{value:,.2f} (%{percent})<extra></extra>",
        )
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=True,
        legend=dict(orientation="v", font=dict(size=11, color=t["text2"])),
        font=dict(size=11),
    )
    return fig

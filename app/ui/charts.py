from __future__ import annotations

from datetime import date, timedelta

import plotly.graph_objects as go

from app import theme
from app.db import get_session
from app.services import budgets as budgets_service
from app.services import forecast, networth, planning
from app.services import transactions as transactions_service
from app.services.money import month_key


def net_worth_figure(*, height: int = 140, months: int = 6) -> go.Figure:
    """Stacked bars: cash contributed vs. gains/losses, with a total line on top."""
    with get_session() as session:
        rows = networth.evolution_breakdown(session, months=months)
    t = theme.current()

    x = [r["month"] for r in rows]
    contributed = [r["contributed_cents"] / 100 for r in rows]
    gains = [r["gain_cents"] / 100 for r in rows]
    totals = [c + g for c, g in zip(contributed, gains)]
    gain_colors = [t["accent2"] if g >= 0 else t["red"] for g in gains]
    show_legend = height >= 180

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=x,
            y=contributed,
            name="Aportado",
            marker=dict(color=t["accent"]),
            hovertemplate="Aportado: R$ %{y:,.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            x=x,
            y=gains,
            name="Ganho/perda",
            marker=dict(color=gain_colors),
            hovertemplate="Ganho/perda: R$ %{y:,.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x,
            y=totals,
            name="Total",
            mode="lines+markers",
            line=dict(color=t["text"], width=1.5),
            marker=dict(size=4, color=t["text"]),
            hovertemplate="Total: R$ %{y:,.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        barmode="relative",
        margin=dict(l=0, r=0, t=28 if show_legend else 4, b=0),
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, color=t["textm"], type="category"),
        yaxis=dict(
            showgrid=True, gridcolor=t["border"], color=t["textm"], zeroline=True,
            zerolinecolor=t["border"],
        ),
        showlegend=show_legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(size=10, color=t["text2"])),
        font=dict(size=11),
    )
    return fig


def monthly_comparison_figure(
    end_month: str, cycle_start_day: int = 1, *, height: int = 180, months: int = 6
) -> go.Figure:
    with get_session() as session:
        rows = transactions_service.monthly_series(
            session, end_month=end_month, months=months, cycle_start_day=cycle_start_day
        )
    t = theme.current()

    x = [r["month"] for r in rows]
    incomes = [r["income_cents"] / 100 for r in rows]
    expenses = [r["expense_cents"] / 100 for r in rows]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=x,
            y=incomes,
            name="Receitas",
            marker=dict(color=t["green"]),
            hovertemplate="Receitas: R$ %{y:,.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            x=x,
            y=expenses,
            name="Despesas",
            marker=dict(color=t["red"]),
            hovertemplate="Despesas: R$ %{y:,.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        barmode="group",
        margin=dict(l=0, r=0, t=28, b=0),
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, color=t["textm"], type="category"),
        yaxis=dict(showgrid=True, gridcolor=t["border"], color=t["textm"], zeroline=False),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(size=10, color=t["text2"])),
        font=dict(size=11),
    )
    return fig


def _daily_expense_std_cents(session) -> float:
    """Rough day-scaled volatility of monthly expenses, used only to shape an
    illustrative uncertainty band - not a statistically calibrated confidence
    interval. Fan charts that claim precise percentiles get misread by lay
    readers as guarantees, so we deliberately keep this qualitative."""
    rows = transactions_service.monthly_series(session, end_month=month_key(date.today()), months=6)
    expenses = [r["expense_cents"] for r in rows if r["expense_cents"] > 0]
    if len(expenses) < 2:
        return 0.0
    mean = sum(expenses) / len(expenses)
    variance = sum((e - mean) ** 2 for e in expenses) / len(expenses)
    return (variance ** 0.5) / 30


def forecast_figure(*, height: int = 200, horizon_days: int = 90) -> go.Figure:
    with get_session() as session:
        series = forecast.project_net_worth(session, horizon_days=horizon_days)
        daily_std = _daily_expense_std_cents(session)
    t = theme.current()
    today = date.today()

    x = [p[0] for p in series]
    y_cents = [p[1] for p in series]
    y = [c / 100 for c in y_cents]

    fig = go.Figure()

    if daily_std > 0:
        days_ahead = [(p[0] - today).days for p in series]
        spread = [daily_std * (max(d, 0) ** 0.5) for d in days_ahead]
        band_wide_hi = [(c + s * 1.6) / 100 for c, s in zip(y_cents, spread)]
        band_wide_lo = [(c - s * 1.6) / 100 for c, s in zip(y_cents, spread)]
        band_narrow_hi = [(c + s * 0.7) / 100 for c, s in zip(y_cents, spread)]
        band_narrow_lo = [(c - s * 0.7) / 100 for c, s in zip(y_cents, spread)]

        fig.add_trace(go.Scatter(x=x, y=band_wide_hi, mode="lines", line=dict(width=0), hoverinfo="skip", showlegend=False))
        fig.add_trace(
            go.Scatter(
                x=x, y=band_wide_lo, mode="lines", line=dict(width=0), fill="tonexty",
                fillcolor=theme.rgba(t["accent2"], 0.07), hoverinfo="skip", showlegend=False,
            )
        )
        fig.add_trace(go.Scatter(x=x, y=band_narrow_hi, mode="lines", line=dict(width=0), hoverinfo="skip", showlegend=False))
        fig.add_trace(
            go.Scatter(
                x=x, y=band_narrow_lo, mode="lines", line=dict(width=0), fill="tonexty",
                fillcolor=theme.rgba(t["accent2"], 0.16), hoverinfo="skip", showlegend=False,
            )
        )

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


def sankey_figure(month: str, cycle_start_day: int = 1, *, height: int = 260) -> go.Figure | None:
    with get_session() as session:
        data = planning.sankey_data(session, month, cycle_start_day)
    if data is None:
        return None
    t = theme.current()

    palette = [t["accent"], t["accent2"], t["amber"], t["green"], t["red"], t["textm"]]
    node_colors = [palette[i % len(palette)] for i in range(len(data["labels"]))]
    link_colors = [theme.rgba(node_colors[s], 0.35) for s in data["source"]]

    fig = go.Figure(
        go.Sankey(
            arrangement="snap",
            node=dict(
                label=data["labels"],
                color=node_colors,
                pad=16,
                thickness=14,
                line=dict(color=t["s1"], width=1),
            ),
            link=dict(
                source=data["source"],
                target=data["target"],
                value=data["value"],
                color=link_colors,
                hovertemplate="%{source.label} -> %{target.label}: R$ %{value:,.2f}<extra></extra>",
            ),
            textfont=dict(color=t["text"], size=12),
        )
    )
    fig.update_layout(
        margin=dict(l=4, r=4, t=8, b=8),
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(size=11),
    )
    return fig

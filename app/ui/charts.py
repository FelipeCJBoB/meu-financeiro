from __future__ import annotations

from datetime import date, timedelta

import plotly.graph_objects as go

from app import theme
from app.db import get_session
from app.services import budgets as budgets_service
from app.services import forecast, networth, planning
from app.services import transactions as transactions_service
from app.services.money import month_key

# Shared bar polish: a 4px rounded data-end reads as a considered mark instead of
# a raw block, and a wider gap between columns is air the eye reads as "breathing
# room" - the single change that most separates a "nice" bar chart from a "cheap"
# one at this data density. bargroupgap only matters when two bars share a slot.
BAR_CORNER_RADIUS = 4
BAR_GAP = 0.35
BAR_GROUP_GAP = 0.12


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
            marker=dict(
                color=t["accent"], cornerradius=BAR_CORNER_RADIUS,
                line=dict(color=t["s1"], width=2),
            ),
            hovertemplate="Aportado: R$ %{y:,.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            x=x,
            y=gains,
            name="Ganho/perda",
            marker=dict(
                color=gain_colors, cornerradius=BAR_CORNER_RADIUS,
                line=dict(color=t["s1"], width=2),
            ),
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
        bargap=BAR_GAP,
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
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(size=theme.FONT["chart_legend"], color=t["text2"])),
        font=dict(size=theme.FONT["chart"], color=t["text2"]),
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
            marker=dict(color=t["green"], cornerradius=BAR_CORNER_RADIUS),
            hovertemplate="Receitas: R$ %{y:,.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            x=x,
            y=expenses,
            name="Despesas",
            marker=dict(color=t["red"], cornerradius=BAR_CORNER_RADIUS),
            hovertemplate="Despesas: R$ %{y:,.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        barmode="group",
        bargap=BAR_GAP,
        bargroupgap=BAR_GROUP_GAP,
        margin=dict(l=0, r=0, t=28, b=0),
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, color=t["textm"], type="category"),
        yaxis=dict(showgrid=True, gridcolor=t["border"], color=t["textm"], zeroline=False),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(size=theme.FONT["chart_legend"], color=t["text2"])),
        font=dict(size=theme.FONT["chart"], color=t["text2"]),
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
        font=dict(size=theme.FONT["chart"], color=t["text2"]),
    )
    return fig


def cashflow_trend_figure(
    end_month: str, cycle_start_day: int = 1, *, height: int = 200, months: int = 12
) -> go.Figure:
    """Net result per cycle: the single line that says whether months end up or down."""
    with get_session() as session:
        rows = transactions_service.monthly_series(
            session, end_month=end_month, months=months, cycle_start_day=cycle_start_day
        )
    t = theme.current()
    x = [r["month"] for r in rows]
    net = [(r["income_cents"] - r["expense_cents"]) / 100 for r in rows]
    colors = [t["pos"] if v >= 0 else t["neg"] for v in net]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=x,
            y=net,
            marker=dict(color=colors, cornerradius=BAR_CORNER_RADIUS),
            hovertemplate="%{x}: R$ %{y:,.2f}<extra></extra>",
        )
    )
    fig.add_hline(y=0, line_width=1, line_color=t["border"])
    fig.update_layout(
        bargap=BAR_GAP,
        margin=dict(l=0, r=0, t=6, b=0),
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, color=t["textm"], type="category"),
        yaxis=dict(showgrid=True, gridcolor=t["border"], color=t["textm"], zeroline=False),
        showlegend=False,
        font=dict(size=theme.FONT["chart"], color=t["text2"]),
    )
    return fig


def category_trend_figure(
    end_month: str, cycle_start_day: int = 1, *, height: int = 220, months: int = 6, top: int = 6
) -> go.Figure | None:
    """Stacked spending by category over time - shows which category is drifting."""
    from app.models import Category, CategoryKind
    from app.services.money import previous_month
    from sqlmodel import select

    labels = [end_month]
    for _ in range(months - 1):
        labels.append(previous_month(labels[-1]))
    labels.reverse()

    with get_session() as session:
        categories = [
            c
            for c in session.exec(select(Category)).all()
            if c.kind != CategoryKind.income and not c.archived
        ]
        series = []
        for category in categories:
            values = [
                budgets_service.spent_in_category(session, category.id, m, cycle_start_day)
                for m in labels
            ]
            if sum(values) > 0:
                series.append(
                    {"name": category.name, "color": category.color, "values": values}
                )

    if not series:
        return None

    ranked = sorted(series, key=lambda row: sum(row["values"]), reverse=True)[:top]
    t = theme.current()

    fig = go.Figure()
    for row in ranked:
        fig.add_trace(
            go.Bar(
                x=labels,
                y=[v / 100 for v in row["values"]],
                name=row["name"],
                # A surface-colour outline is how a stacked bar fakes the 2px gap
                # between segments - Plotly has no native inter-segment spacing.
                marker=dict(
                    color=row["color"], cornerradius=BAR_CORNER_RADIUS,
                    line=dict(color=t["s1"], width=2),
                ),
                hovertemplate=f"{row['name']}: R$ %{{y:,.2f}}<extra></extra>",
            )
        )
    fig.update_layout(
        barmode="stack",
        bargap=BAR_GAP,
        margin=dict(l=0, r=0, t=30, b=0),
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, color=t["textm"], type="category"),
        yaxis=dict(showgrid=True, gridcolor=t["border"], color=t["textm"], zeroline=False),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, x=0,
            font=dict(size=theme.FONT["chart_legend"], color=t["text2"]),
        ),
        font=dict(size=theme.FONT["chart"], color=t["text2"]),
    )
    return fig


def savings_rate_trend_figure(
    end_month: str, cycle_start_day: int = 1, *, height: int = 200, months: int = 12
) -> go.Figure:
    """Savings rate per cycle - the discipline curve."""
    with get_session() as session:
        rows = transactions_service.monthly_series(
            session, end_month=end_month, months=months, cycle_start_day=cycle_start_day
        )
    t = theme.current()
    x, y = [], []
    for row in rows:
        if row["income_cents"] > 0:
            x.append(row["month"])
            y.append(
                (row["income_cents"] - row["expense_cents"]) / row["income_cents"] * 100
            )

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x,
            y=y,
            mode="lines+markers",
            line=dict(color=t["accent2"], width=2),
            marker=dict(size=6, color=t["accent2"]),
            fill="tozeroy",
            fillcolor=theme.rgba(t["accent2"], 0.12),
            hovertemplate="%{x}: %{y:.0f}%<extra></extra>",
        )
    )
    fig.add_hline(
        y=20, line_width=1, line_dash="dash", line_color=t["textm"],
        annotation_text="referencia 20%",
        annotation_font=dict(size=theme.FONT["chart"], color=t["textm"]),
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=6, b=0),
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, color=t["textm"], type="category"),
        yaxis=dict(
            showgrid=True, gridcolor=t["border"], color=t["textm"],
            zeroline=True, zerolinecolor=t["border"], ticksuffix="%",
        ),
        showlegend=False,
        font=dict(size=theme.FONT["chart"], color=t["text2"]),
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
            marker=dict(color=theme.rgba(t["textm"], 0.25), cornerradius=BAR_CORNER_RADIUS),
            hovertemplate="%{y} · orcado: R$ %{x:,.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            y=names,
            x=spent_vals,
            name="Gasto",
            orientation="h",
            marker=dict(color=colors, cornerradius=BAR_CORNER_RADIUS),
            hovertemplate="%{y} · gasto: R$ %{x:,.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        barmode="group",
        bargap=BAR_GAP,
        bargroupgap=BAR_GROUP_GAP,
        margin=dict(l=0, r=0, t=28, b=0),
        height=max(160, len(rows) * 46 + 40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=True, gridcolor=t["border"], color=t["textm"], zeroline=False),
        yaxis=dict(showgrid=False, color=t["text"]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(size=theme.FONT["chart_legend"], color=t["text2"])),
        font=dict(size=theme.FONT["chart"], color=t["text2"]),
    )
    return fig


def composition_donut_figure(*, height: int = 220) -> go.Figure:
    with get_session() as session:
        rows = networth.balance_sheet(session)["assets"]
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
            textfont=dict(color="#ffffff", size=theme.FONT["chart"]),
            hovertemplate="%{label}: R$ %{value:,.2f} (%{percent})<extra></extra>",
        )
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=True,
        legend=dict(orientation="v", font=dict(size=theme.FONT["chart_legend"], color=t["text2"])),
        font=dict(size=theme.FONT["chart"], color=t["text2"]),
    )
    return fig


def budget_history_figure(
    end_month: str, cycle_start_day: int = 1, *, height: int = 200, months: int = 6
) -> go.Figure:
    with get_session() as session:
        rows = budgets_service.budget_history(
            session, end_month=end_month, months=months, cycle_start_day=cycle_start_day
        )
    t = theme.current()
    x = [r["month"] for r in rows]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=x,
            y=[r["budget_cents"] / 100 for r in rows],
            name="Orcado",
            marker=dict(color=theme.rgba(t["textm"], 0.30), cornerradius=BAR_CORNER_RADIUS),
            hovertemplate="Orcado: R$ %{y:,.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            x=x,
            y=[r["spent_cents"] / 100 for r in rows],
            name="Gasto",
            marker=dict(color=t["accent"], cornerradius=BAR_CORNER_RADIUS),
            hovertemplate="Gasto: R$ %{y:,.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        barmode="group",
        bargap=BAR_GAP,
        bargroupgap=BAR_GROUP_GAP,
        margin=dict(l=0, r=0, t=28, b=0),
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, color=t["textm"], type="category"),
        yaxis=dict(showgrid=True, gridcolor=t["border"], color=t["textm"], zeroline=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(size=theme.FONT["chart_legend"], color=t["text2"])),
        font=dict(size=theme.FONT["chart"], color=t["text2"]),
    )
    return fig


def goal_progress_figure(goal, *, height: int = 200) -> go.Figure:
    from app.services import goals as goals_service

    with get_session() as session:
        series = goals_service.progress_series(session, goal)
    t = theme.current()

    fig = go.Figure()
    if series["planned_dates"]:
        fig.add_trace(
            go.Scatter(
                x=series["planned_dates"],
                y=[v / 100 for v in series["planned_values"]],
                mode="lines",
                name="Planejado",
                line=dict(color=t["textm"], width=1.5, dash="dash"),
                hovertemplate="Planejado: R$ %{y:,.2f}<extra></extra>",
            )
        )
    fig.add_trace(
        go.Scatter(
            x=series["actual_dates"],
            y=[v / 100 for v in series["actual_values"]],
            mode="lines+markers",
            name="Real",
            line=dict(color=t["accent"], width=2, shape="hv"),
            marker=dict(size=5, color=t["accent"]),
            hovertemplate="Real: R$ %{y:,.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=28, b=0),
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, color=t["textm"], type="date"),
        yaxis=dict(showgrid=True, gridcolor=t["border"], color=t["textm"], zeroline=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(size=theme.FONT["chart_legend"], color=t["text2"])),
        font=dict(size=theme.FONT["chart"], color=t["text2"]),
    )
    return fig


def sankey_figure(
    month: str,
    cycle_start_day: int = 1,
    *,
    height: int = 260,
    start=None,
    end=None,
    account_id=None,
) -> go.Figure | None:
    with get_session() as session:
        data = planning.sankey_data(
            session, month, cycle_start_day, start=start, end=end, account_id=account_id
        )
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
            textfont=dict(color=t["text"], size=theme.FONT["chart"]+1),
        )
    )
    fig.update_layout(
        margin=dict(l=4, r=4, t=8, b=8),
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(size=theme.FONT["chart"], color=t["text2"]),
    )
    return fig

from __future__ import annotations

from nicegui import ui

from app import state, theme
from app.db import get_session
from app.models import CategoryKind
from app.services import budgets as budgets_service
from app.services import categories as categories_service
from app.services.money import format_brl, to_cents
from app.ui import components
from app.ui.charts import budget_comparison_figure
from app.ui.layout import page_frame


def _category_row(category, month: str, cycle_start_day: int) -> None:
    with get_session() as session:
        budget = budgets_service.get_budget(session, category.id, month)
        spent_cents = budgets_service.spent_in_category(
            session, category.id, month, cycle_start_day
        )
    budget_cents = budget.amount_cents if budget else 0
    pct = (spent_cents / budget_cents) if budget_cents else 0.0

    with ui.column().style("width:100%;gap:6px;margin-bottom:14px"):
        with ui.row().style("width:100%;align-items:center;gap:10px"):
            components.category_chip(category.icon, category.color, size="26px")
            ui.label(category.name).style(f"font-size:13px;color:{theme.var('text')};flex:1")
            ui.label(f"{format_brl(spent_cents)} de").style(
                f"font-size:12px;color:{theme.var('text2')}"
            )
            budget_input = ui.number(
                value=budget_cents / 100 if budget_cents else None,
                format="%.2f",
                placeholder="definir",
            ).props("outlined dense").style("width:110px")

            def _save(category_id=category.id) -> None:
                with get_session() as s2:
                    budgets_service.set_budget(
                        s2,
                        category_id=category_id,
                        month=month,
                        amount_cents=to_cents(budget_input.value or 0),
                    )
                ui.navigate.reload()

            budget_input.on("blur", _save)

        if budget_cents:
            color = theme.var(components.status_color_key(pct))
            components.progress_track(pct, color)
        else:
            components.progress_track(0, theme.var("border"))


def render() -> None:
    with page_frame("/orcamento"):
        month = state.current_month()
        cycle_start_day = state.cycle_start_day()

        with get_session() as session:
            categories = [
                c
                for c in categories_service.list_categories(session)
                if c.kind != CategoryKind.income
            ]
            summary = budgets_service.month_summary(session, month, cycle_start_day)
            pace = budgets_service.spend_pace(session, month, cycle_start_day)

        with ui.row().style("width:100%;justify-content:space-between;align-items:center"):
            components.month_navigator()
            if summary["budget_cents"]:
                pct = summary["spent_cents"] / summary["budget_cents"]
                ui.label(
                    f"{format_brl(summary['spent_cents'])} de {format_brl(summary['budget_cents'])} ({pct * 100:.0f}%)"
                ).style(f"font-size:13px;color:{theme.var('text')}")

        if pace:
            over = pace["over_by_cents"]
            with components.card():
                with ui.row().style("align-items:center;gap:8px"):
                    ui.icon("insights").style(
                        f"color:{theme.var('red') if over > 0 else theme.var('green')};font-size:18px"
                    )
                    text = (
                        f"No ritmo atual (dia {pace['days_elapsed']} de {pace['days_in_month']}), "
                        f"voce deve {'ultrapassar' if over > 0 else 'fechar dentro do'} orcamento"
                        f"{f' em {format_brl(abs(over))}' if over > 0 else ''}"
                        f" · projecao {format_brl(pace['projected_cents'])}"
                    )
                    ui.label(text).style(f"font-size:13px;color:{theme.var('text')}")

        if summary["budget_cents"]:
            with components.card():
                components.section_label(
                    "Orcado vs. gasto por categoria",
                    help_text=(
                        "Barra cinza = quanto voce planejou gastar. Barra colorida = quanto "
                        "ja gastou (verde dentro do previsto, amarelo perto do limite, "
                        "vermelho estourado)."
                    ),
                )
                ui.plotly(budget_comparison_figure(month, cycle_start_day)).style("width:100%")

        with components.card():
            components.section_label(
                "Categorias",
                help_text="Clique no valor para definir ou editar o orcamento de cada categoria.",
            )
            if not categories:
                components.empty_state("Nenhuma categoria de despesa ainda", icon="pie_chart")
            for category in categories:
                _category_row(category, month, cycle_start_day)

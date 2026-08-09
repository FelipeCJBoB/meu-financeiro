from __future__ import annotations

from nicegui import ui

from app import state, theme
from app.db import get_session
from app.models import Category, CategoryKind
from app.services import budgets as budgets_service
from app.services import categories as categories_service
from app.services.money import format_brl, format_month_label, previous_month, to_cents
from app.ui import components
from app.ui.charts import budget_comparison_figure, budget_history_figure
from app.ui.layout import page_frame


def _category_transactions_dialog(category: Category, month: str, cycle_start_day: int) -> ui.dialog:
    with get_session() as session:
        items = budgets_service.category_transactions(session, category.id, month, cycle_start_day)
        rows = [
            {
                "date": tx.date.strftime("%d/%m"),
                "description": tx.description,
                "amount_cents": tx.amount_cents,
            }
            for tx in items
        ]

    with ui.dialog() as dialog, components.card(padding="1.25rem"):
        ui.label(f"{category.name} · {format_month_label(month)}").style(
            f"font-size:15px;font-weight:500;color:{theme.var('text')}"
        )
        ui.label(f"{len(rows)} lancamento(s) compoem esse gasto").style(
            f"font-size:14px;color:{theme.var('textm')};margin:4px 0 10px"
        )
        if not rows:
            components.empty_state("Nenhum lancamento nesta categoria", icon="receipt_long")
        for row in rows:
            with ui.row().style(
                f"width:100%;align-items:center;gap:10px;padding:7px 0;"
                f"border-bottom:0.5px solid {theme.var('border')};min-width:340px"
            ):
                ui.label(row["date"]).style(f"font-size:14px;color:{theme.var('textm')}")
                ui.label(row["description"]).style(
                    f"font-size:15px;color:{theme.var('text')};flex:1"
                )
                ui.label(f"-{format_brl(row['amount_cents'])}").style(
                    f"font-size:15px;color:{theme.var('red')}"
                )
        with ui.row().style("justify-content:flex-end;margin-top:12px;width:100%"):
            ui.button("Fechar", on_click=dialog.close).props("flat no-caps").style(
                f"color:{theme.var('text2')}"
            )
    return dialog


def _category_row(category, month: str, cycle_start_day: int) -> None:
    with get_session() as session:
        budget = budgets_service.get_budget(session, category.id, month)
        spent_cents = budgets_service.spent_in_category(
            session, category.id, month, cycle_start_day
        )
        pace = budgets_service.category_pace(session, category.id, month, cycle_start_day)
    budget_cents = budget.amount_cents if budget else 0
    pct = (spent_cents / budget_cents) if budget_cents else 0.0
    remaining = budget_cents - spent_cents

    with ui.column().style("width:100%;gap:6px;margin-bottom:16px"):
        with ui.row().style("width:100%;align-items:center;gap:10px"):
            components.category_chip(category.icon, category.color, size="26px")
            name_label = ui.label(category.name).style(
                f"font-size:15px;color:{theme.var('text')};flex:1;cursor:pointer"
            )
            drill = _category_transactions_dialog(category, month, cycle_start_day)
            name_label.on("click", drill.open)
            name_label.tooltip("Ver os lancamentos desta categoria")

            ui.label(f"{format_brl(spent_cents)} de").style(
                f"font-size:14px;color:{theme.var('text2')}"
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
            with ui.row().style("width:100%;justify-content:space-between;margin-top:2px"):
                if remaining >= 0:
                    ui.label(f"{format_brl(remaining)} restantes").style(
                        f"font-size:13px;color:{theme.var('textm')}"
                    )
                else:
                    ui.label(f"{format_brl(abs(remaining))} acima do limite").style(
                        f"font-size:15px;color:{theme.var('red')}"
                    )
                if pace and pace["over_by_cents"] > 0:
                    ui.label(
                        f"No ritmo atual, estoura em {format_brl(pace['over_by_cents'])}"
                    ).style(f"font-size:15px;color:{theme.var('amber')}")
                elif pace:
                    ui.label(
                        f"Projecao: {format_brl(pace['projected_cents'])} ate o fim do ciclo"
                    ).style(f"font-size:13px;color:{theme.var('textm')}")
        else:
            components.progress_track(0, theme.var("border"))


def _unbudgeted_section(month: str, cycle_start_day: int) -> None:
    with get_session() as session:
        rows = budgets_service.unbudgeted_categories(session, month, cycle_start_day)
    if not rows:
        return

    with components.card():
        components.section_label(
            "Gastos sem orcamento definido",
            help_text=(
                "Categorias em que voce gastou neste ciclo mas ainda nao definiu limite. "
                "A sugestao vem da sua propria media dos ciclos anteriores."
            ),
        )
        for row in rows:
            category = row["category"]
            with ui.row().style(
                f"width:100%;align-items:center;gap:10px;padding:8px 0;"
                f"border-bottom:0.5px solid {theme.var('border')}"
            ):
                components.category_chip(category.icon, category.color, size="26px")
                with ui.column().style("flex:1;gap:0"):
                    ui.label(category.name).style(f"font-size:15px;color:{theme.var('text')}")
                    ui.label(f"Gasto neste ciclo: {format_brl(row['spent_cents'])}").style(
                        f"font-size:13px;color:{theme.var('textm')}"
                    )

                suggested = row["suggested_cents"]

                def _apply(category_id=category.id, amount=suggested) -> None:
                    with get_session() as s2:
                        budgets_service.set_budget(
                            s2, category_id=category_id, month=month, amount_cents=amount
                        )
                    ui.navigate.reload()

                ui.button(
                    f"Definir {format_brl(suggested)}", on_click=_apply
                ).props("flat dense no-caps").style(
                    f"color:{theme.var('accent2')};font-size:14px"
                )


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
            has_previous = bool(
                budgets_service.month_summary(session, previous_month(month), cycle_start_day)[
                    "budget_cents"
                ]
            )

        with ui.row().style(
            "width:100%;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px"
        ):
            components.month_navigator()
            with ui.row().style("gap:8px;align-items:center"):
                if has_previous:

                    def _copy() -> None:
                        with get_session() as s2:
                            copied = budgets_service.copy_from_previous_month(s2, month)
                        ui.notify(
                            f"{copied} orcamento(s) copiado(s) do ciclo anterior"
                            if copied
                            else "Nada novo para copiar",
                        )
                        ui.navigate.reload()

                    ui.button(
                        "Copiar do ciclo anterior", icon="content_copy", on_click=_copy
                    ).props("flat no-caps dense").style(
                        f"color:{theme.var('text2')}"
                    ).tooltip("Traz os limites do ciclo anterior para este, sem sobrescrever o que ja existe")

        remaining_total = summary["budget_cents"] - summary["spent_cents"]
        with components.kpi_grid():
            components.kpi_card(
                "Total orcado",
                format_brl(summary["budget_cents"]),
                help_text="Soma dos limites definidos nas categorias deste ciclo.",
            )
            components.kpi_card(
                "Total gasto",
                format_brl(summary["spent_cents"]),
                sub=(
                    f"{summary['spent_cents'] / summary['budget_cents'] * 100:.0f}% do orcado"
                    if summary["budget_cents"]
                    else "Nenhum orcamento definido"
                ),
                value_color=(
                    theme.var("red")
                    if summary["budget_cents"] and summary["spent_cents"] > summary["budget_cents"]
                    else theme.var("text")
                ),
            )
            components.kpi_card(
                "Ainda disponivel",
                format_brl(remaining_total),
                value_color=theme.var("green") if remaining_total >= 0 else theme.var("red"),
                help_text="Total orcado menos o que ja foi gasto neste ciclo.",
            )
            if pace:
                over = pace["over_by_cents"]
                components.kpi_card(
                    "Projecao do ciclo",
                    format_brl(pace["projected_cents"]),
                    sub=f"dia {pace['days_elapsed']} de {pace['days_in_month']}",
                    value_color=theme.var("red") if over > 0 else theme.var("green"),
                    delta_text=(
                        f"{'Acima' if over > 0 else 'Dentro'} do orcamento em {format_brl(abs(over))}"
                    ),
                    delta_color=theme.var("red") if over > 0 else theme.var("green"),
                    help_text="Gasto ate hoje extrapolado linearmente ate o fim do ciclo.",
                )

        _unbudgeted_section(month, cycle_start_day)

        with components.panel_grid():
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
                    "Orcado vs. gasto nos ultimos ciclos",
                    help_text=(
                        "Se o gasto passa do orcado todo mes, o orcamento nao esta realista - "
                        "ajuste o limite em vez de brigar com ele."
                    ),
                )
                ui.plotly(
                    budget_history_figure(month, cycle_start_day, height=200)
                ).style("width:100%;height:200px")

        with components.card():
            components.section_label(
                "Categorias",
                help_text=(
                    "Clique no valor para definir o limite. Clique no nome da categoria para "
                    "ver os lancamentos que formam aquele gasto."
                ),
            )
            if not categories:
                components.empty_state("Nenhuma categoria de despesa ainda", icon="pie_chart")
            for category in categories:
                _category_row(category, month, cycle_start_day)

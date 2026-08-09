from __future__ import annotations

from nicegui import ui

from app import state, theme
from app.db import get_session
from app.models import Category, TransactionType
from app.services import accounts, budgets, goals, networth, planning, transactions
from app.services.money import format_brl, month_bounds, previous_month
from app.ui import components
from app.ui.charts import net_worth_figure
from app.ui.layout import page_frame


def _transaction_row(session, tx) -> None:
    with ui.row().style(
        f"width:100%;align-items:center;gap:10px;padding:8px 0;"
        f"border-bottom:0.5px solid {theme.var('border')}"
    ):
        if tx.type == TransactionType.transfer:
            components.category_chip("swap_horiz", theme.current()["accent2"])
            sub = "Transferencia"
        else:
            category = session.get(Category, tx.category_id) if tx.category_id else None
            components.category_chip(
                category.icon if category else "receipt_long",
                category.color if category else theme.current()["textm"],
            )
            sub = category.name if category else "Sem categoria"

        with ui.column().style("flex:1;gap:0"):
            ui.label(tx.description).style(f"font-size:13px;color:{theme.var('text')}")
            ui.label(f"{tx.date.strftime('%d/%m')} · {sub}").style(
                f"font-size:11px;color:{theme.var('textm')}"
            )

        if tx.type == TransactionType.income:
            color, sign = theme.var("green"), "+"
        elif tx.type == TransactionType.transfer:
            color, sign = theme.var("text2"), ""
        else:
            color, sign = theme.var("red"), "-"
        ui.label(f"{sign}{format_brl(tx.amount_cents)}").style(f"font-size:13px;color:{color}")


def render() -> None:
    with page_frame("/"):
        with get_session() as session:
            all_accounts = accounts.list_accounts(session)

            if not all_accounts:
                with components.card(padding="2rem"):
                    components.empty_state(
                        "Nenhuma conta cadastrada ainda. Crie a primeira conta para comecar.",
                        icon="account_balance_wallet",
                    )
                    with ui.row().style("justify-content:center;width:100%;margin-top:8px"):
                        dialog = components.new_account_dialog(lambda: ui.navigate.reload())
                        ui.button("Criar conta", on_click=dialog.open).props(
                            "no-caps unelevated"
                        ).style(f"background:{theme.var('accent')};color:{theme.var('s1')}")
                return

            total_net_worth, _ = networth.current_net_worth(session)
            month = state.current_month()
            cycle_start_day = state.cycle_start_day()
            totals = transactions.month_totals(session, month, cycle_start_day)
            cash_flow = totals["income_cents"] - totals["expense_cents"]
            summary = budgets.month_summary(session, month, cycle_start_day)
            budget_pct = (
                summary["spent_cents"] / summary["budget_cents"] if summary["budget_cents"] else 0.0
            )

            prev_totals = transactions.month_totals(
                session, previous_month(month), cycle_start_day
            )
            prev_cash_flow = prev_totals["income_cents"] - prev_totals["expense_cents"]
            cash_flow_delta = cash_flow - prev_cash_flow
            if prev_totals["income_cents"] or prev_totals["expense_cents"]:
                arrow = "▲" if cash_flow_delta >= 0 else "▼"
                delta_text = f"{arrow} {format_brl(abs(cash_flow_delta))} vs mes anterior"
                delta_color = theme.var("green") if cash_flow_delta >= 0 else theme.var("red")
            else:
                delta_text, delta_color = "", None

            pace = budgets.spend_pace(session, month, cycle_start_day)
            available = planning.available_to_spend(session, month, cycle_start_day)

            components.month_navigator()

            with ui.row().style("width:100%;gap:12px;flex-wrap:wrap"):
                if available:
                    free = available["available_cents"]
                    components.kpi_card(
                        "Disponivel para gastar",
                        format_brl(free),
                        sub=(
                            f"Receita {format_brl(available['income_total_cents'])} - "
                            f"compromissos {format_brl(available['committed_cents'])}"
                        ),
                        value_color=theme.var("green") if free >= 0 else theme.var("red"),
                        help_text=(
                            "Receita recebida + recorrencias de entrada ainda a vencer, menos "
                            "despesas ja pagas, contas fixas a vencer e o quanto voce precisa "
                            "guardar este mes para suas metas com prazo."
                        ),
                    )
                components.kpi_card(
                    "Patrimonio liquido",
                    format_brl(total_net_worth),
                    help_text="Soma dos saldos calculados de todas as suas contas ativas, agora.",
                )
                components.kpi_card(
                    "Fluxo do mes",
                    format_brl(cash_flow),
                    sub=f"Receitas {format_brl(totals['income_cents'])} · Despesas {format_brl(totals['expense_cents'])}",
                    value_color=theme.var("green") if cash_flow >= 0 else theme.var("red"),
                    delta_text=delta_text,
                    delta_color=delta_color,
                    help_text="Receitas menos despesas ja lancadas neste ciclo (nao inclui recorrencias futuras).",
                )
                if pace:
                    over = pace["over_by_cents"]
                    components.kpi_card(
                        "Ritmo de gasto",
                        format_brl(pace["projected_cents"]),
                        sub=f"Projetado p/ fim do mes (dia {pace['days_elapsed']} de {pace['days_in_month']})",
                        value_color=theme.var("red") if over > 0 else theme.var("green"),
                        delta_text=(
                            f"{'Acima' if over > 0 else 'Dentro'} do orcamento em {format_brl(abs(over))}"
                        ),
                        delta_color=theme.var("red") if over > 0 else theme.var("green"),
                        help_text=(
                            "Projecao linear: gasto ate hoje dividido pelos dias decorridos, "
                            "multiplicado pelos dias do ciclo. Assume que voce vai continuar "
                            "gastando no mesmo ritmo ate o fim do mes."
                        ),
                    )
                else:
                    components.kpi_card(
                        "Orcamento do mes",
                        f"{budget_pct * 100:.0f}%" if summary["budget_cents"] else "--",
                        sub=(
                            f"{format_brl(summary['spent_cents'])} de {format_brl(summary['budget_cents'])}"
                            if summary["budget_cents"]
                            else "Nenhum orcamento definido"
                        ),
                        help_text="Percentual do total orcado nas categorias que ja foi gasto neste ciclo.",
                    )

            with ui.row().style("width:100%;gap:16px;flex-wrap:wrap;align-items:stretch"):
                with ui.column().style("flex:1.3;min-width:280px;gap:8px"):
                    with components.card():
                        components.section_label(
                            "Patrimonio nos ultimos 6 meses",
                            help_text="Baseado nos snapshots que voce registra manualmente na tela Patrimonio.",
                        )
                        ui.plotly(net_worth_figure(height=140)).style("width:100%;height:140px")

                with ui.column().style("flex:1;min-width:240px;gap:8px"):
                    with components.card():
                        components.section_label("Metas em andamento")
                        goal_list = goals.list_goals(session)[:2]
                        if not goal_list:
                            components.empty_state("Nenhuma meta ainda", icon="flag")
                        for goal in goal_list:
                            pct = goals.progress_pct(goal)
                            with ui.row().style(
                                "width:100%;justify-content:space-between;"
                                "font-size:13px;margin-bottom:4px"
                            ):
                                ui.label(goal.name).style(f"color:{theme.var('text')}")
                                ui.label(f"{pct * 100:.0f}%").style(f"color:{theme.var('text2')}")
                            components.progress_track(pct, theme.var("accent"))

            with components.card():
                components.section_label("Lancamentos do mes")
                start, end = month_bounds(month, cycle_start_day)
                recent = transactions.list_transactions(session, start=start, end=end, limit=8)
                if not recent:
                    components.empty_state("Nenhum lancamento neste mes", icon="receipt_long")
                for tx in recent:
                    _transaction_row(session, tx)

from __future__ import annotations

from nicegui import ui

from app import state, theme
from app.db import get_session
from app.models import Account, Category, TransactionType
from app.services import accounts, budgets, goals, networth, planning, recurring, transactions
from app.services.money import (
    PERIOD_LABELS,
    PERIOD_MONTHS,
    format_brl,
    period_bounds,
    previous_month,
)
from app.ui import components
from app.ui.charts import monthly_comparison_figure, net_worth_figure, sankey_figure
from app.ui.layout import page_frame


def _transaction_row(session, tx) -> None:
    with ui.row().style(
        f"width:100%;align-items:center;gap:10px;padding:8px 0;"
        f"border-bottom:0.5px solid {theme.var('border')}"
    ):
        if tx.type == TransactionType.transfer:
            components.category_chip("swap_horiz", theme.current()["accent2"])
            sub = "Transferencia"
        elif tx.type == TransactionType.adjustment:
            components.category_chip("tune", theme.current()["textm"])
            sub = "Ajuste de saldo"
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
            color, sign, shown_cents = theme.var("green"), "+", tx.amount_cents
        elif tx.type == TransactionType.transfer:
            color, sign, shown_cents = theme.var("text2"), "", tx.amount_cents
        elif tx.type == TransactionType.adjustment:
            color = theme.var("green") if tx.amount_cents >= 0 else theme.var("red")
            sign = "+" if tx.amount_cents >= 0 else "-"
            shown_cents = abs(tx.amount_cents)
        else:
            color, sign, shown_cents = theme.var("red"), "-", tx.amount_cents
        ui.label(f"{sign}{format_brl(shown_cents)}").style(f"font-size:13px;color:{color}")


def _exception_banner(session, status: dict, on_changed) -> None:
    """Dark-cockpit style: silent when everything is fine, only shows for real exceptions."""
    if status["level"] == "ok":
        return

    t = theme.current()
    raw = t["red"] if status["level"] == "critical" else t["amber"]
    accent = theme.var("red") if status["level"] == "critical" else theme.var("amber")
    icon = "error" if status["level"] == "critical" else "warning"

    with ui.column().style(
        f"width:100%;border:1px solid {accent};border-radius:12px;padding:1rem 1.25rem;"
        f"background:{theme.rgba(raw, 0.06)};gap:8px"
    ):
        with ui.row().style("align-items:center;gap:8px"):
            ui.icon(icon).style(f"color:{accent};font-size:18px")
            ui.label("Precisa da sua atencao").style(
                f"font-size:14px;font-weight:500;color:{theme.var('text')}"
            )

        if status["available_negative"]:
            ui.label("Disponivel para gastar esta negativo neste ciclo.").style(
                f"font-size:13px;color:{theme.var('text2')}"
            )

        for rule in status["overdue_rules"]:
            with ui.row().style(
                f"width:100%;align-items:center;gap:10px;padding:6px 0;"
                f"border-top:0.5px solid {theme.var('border')}"
            ):
                with ui.column().style("flex:1;gap:0"):
                    ui.label(f"Vencida: {rule.description}").style(
                        f"font-size:13px;color:{theme.var('text')}"
                    )
                    ui.label(
                        f"Venceu em {rule.next_due_date.strftime('%d/%m/%Y')} · {format_brl(rule.amount_cents)}"
                    ).style(f"font-size:11px;color:{theme.var('textm')}")
                confirm_dialog = components.confirm_recurring_dialog(rule, on_changed)
                ui.button("Confirmar", on_click=confirm_dialog.open).props(
                    "dense no-caps unelevated"
                ).style(f"background:{theme.var('accent')};color:{theme.var('s1')}")

        for row in status["over_budget_categories"]:
            with ui.row().style(
                f"width:100%;align-items:center;gap:10px;padding:6px 0;"
                f"border-top:0.5px solid {theme.var('border')}"
            ):
                category = row["category"]
                ui.label(
                    f"{category.name} passou do orcamento: {format_brl(row['spent_cents'])} "
                    f"de {format_brl(row['budget_cents'])}"
                ).style(f"font-size:13px;color:{theme.var('text2')};flex:1")


def _upcoming_payments_section(session) -> None:
    upcoming = recurring.upcoming_recurring_rules(session, within_days=30)
    with components.card():
        components.section_label(
            "Proximos pagamentos",
            help_text="Recorrencias ativas com vencimento nos proximos 30 dias, ainda nao vencidas.",
        )
        if not upcoming:
            components.empty_state("Nada agendado nos proximos 30 dias", icon="event_available")
        for rule in upcoming:
            account = session.get(Account, rule.account_id)
            with ui.row().style(
                f"width:100%;align-items:center;gap:10px;padding:8px 0;"
                f"border-bottom:0.5px solid {theme.var('border')}"
            ):
                components.category_chip(
                    "arrow_circle_up" if rule.type == TransactionType.income else "event_repeat",
                    theme.current()["accent"] if rule.type == TransactionType.income else theme.current()["textm"],
                )
                with ui.column().style("flex:1;gap:0"):
                    ui.label(rule.description).style(f"font-size:13px;color:{theme.var('text')}")
                    account_name = account.name if account else ""
                    ui.label(
                        f"em {rule.next_due_date.strftime('%d/%m')} · {account_name}"
                    ).style(f"font-size:11px;color:{theme.var('textm')}")
                color = theme.var("green") if rule.type == TransactionType.income else theme.var("text2")
                sign = "+" if rule.type == TransactionType.income else "-"
                ui.label(f"{sign}{format_brl(rule.amount_cents)}").style(
                    f"font-size:13px;color:{color}"
                )


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

            month = state.current_month()
            cycle_start_day = state.cycle_start_day()
            period = state.period()
            is_month_view = period == "month"
            period_label = PERIOD_LABELS[period].lower()
            period_months = PERIOD_MONTHS[period]

            start, end = period_bounds(period, month, cycle_start_day)
            totals = transactions.range_totals(session, start, end)
            cash_flow = totals["income_cents"] - totals["expense_cents"]

            sheet = networth.balance_sheet(session)
            total_net_worth = sheet["net_worth_cents"]
            summary = budgets.month_summary(session, month, cycle_start_day)
            budget_pct = (
                summary["spent_cents"] / summary["budget_cents"] if summary["budget_cents"] else 0.0
            )

            prev_start, prev_end = period_bounds(
                period, previous_month(month), cycle_start_day
            )
            prev_totals = transactions.range_totals(session, prev_start, prev_end)
            prev_cash_flow = prev_totals["income_cents"] - prev_totals["expense_cents"]
            cash_flow_delta = cash_flow - prev_cash_flow
            if prev_totals["income_cents"] or prev_totals["expense_cents"]:
                arrow = "▲" if cash_flow_delta >= 0 else "▼"
                pct_text = (
                    f" ({abs(cash_flow_delta) / abs(prev_cash_flow) * 100:.0f}%)"
                    if prev_cash_flow
                    else ""
                )
                delta_text = (
                    f"{arrow} {format_brl(abs(cash_flow_delta))}{pct_text} vs periodo anterior"
                )
                delta_color = theme.var("green") if cash_flow_delta >= 0 else theme.var("red")
            else:
                delta_text, delta_color = "", None

            pace = budgets.spend_pace(session, month, cycle_start_day)
            available = planning.available_to_spend(session, month, cycle_start_day)
            allowance = planning.daily_allowance(session, month, cycle_start_day)
            status = planning.overall_status(session, month, cycle_start_day)
            emergency = planning.emergency_fund_months(session, month, cycle_start_day)
            period_savings_rate = planning.savings_rate(session, start, end)
            worst_category = planning.worst_budget_category(session, month, cycle_start_day)
            trend_points = networth.trend(session, months=2)

            with ui.row().style(
                "width:100%;justify-content:space-between;align-items:center;"
                "flex-wrap:wrap;gap:8px"
            ):
                components.period_selector()
                if is_month_view:
                    components.month_navigator()
                else:
                    ui.label(
                        f"{start.strftime('%d/%m/%Y')} até {end.strftime('%d/%m/%Y')}"
                    ).style(f"font-size:13px;color:{theme.var('text2')}")

            _exception_banner(session, status, lambda: ui.navigate.reload())

            with components.kpi_grid():
                if available:
                    free = available["available_cents"]
                    allowance_text = (
                        f"{format_brl(allowance['per_day_cents'])}/dia nos {allowance['days_remaining']} dias restantes"
                        if allowance
                        else ""
                    )
                    components.kpi_card(
                        "Disponivel para gastar",
                        format_brl(free),
                        sub=(
                            f"Receita {format_brl(available['income_total_cents'])} - "
                            f"compromissos {format_brl(available['committed_cents'])}"
                        ),
                        value_color=theme.var("green") if free >= 0 else theme.var("red"),
                        delta_text=allowance_text,
                        help_text=(
                            "Receita recebida + recorrencias de entrada ainda a vencer, menos "
                            "despesas ja pagas, contas fixas a vencer e o quanto voce precisa "
                            "guardar este mes para suas metas com prazo. O segundo valor divide "
                            "isso pelos dias que faltam no ciclo."
                        ),
                    )
                previous_net_worth = trend_points[0][1] if len(trend_points) > 1 else None
                if previous_net_worth:
                    nw_delta = total_net_worth - previous_net_worth
                    nw_arrow = "▲" if nw_delta >= 0 else "▼"
                    nw_delta_text = (
                        f"{nw_arrow} {format_brl(abs(nw_delta))} "
                        f"({abs(nw_delta) / abs(previous_net_worth) * 100:.1f}%) vs snapshot anterior"
                    )
                    nw_delta_color = theme.var("green") if nw_delta >= 0 else theme.var("red")
                else:
                    nw_delta_text, nw_delta_color = "", None

                components.kpi_card(
                    "Patrimonio liquido",
                    format_brl(total_net_worth),
                    sub=f"Ativos {format_brl(sheet['assets_cents'])} - dividas {format_brl(sheet['liabilities_cents'])}",
                    delta_text=nw_delta_text,
                    delta_color=nw_delta_color,
                    help_text="Tudo que voce tem menos tudo que voce deve.",
                )
                components.kpi_card(
                    f"Fluxo · {period_label}",
                    format_brl(cash_flow),
                    sub=f"Receitas {format_brl(totals['income_cents'])} · Despesas {format_brl(totals['expense_cents'])}",
                    value_color=theme.var("green") if cash_flow >= 0 else theme.var("red"),
                    delta_text=delta_text,
                    delta_color=delta_color,
                    help_text=(
                        "Receitas menos despesas lancadas no periodo selecionado "
                        "(nao inclui recorrencias futuras)."
                    ),
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

            with components.kpi_grid():
                if emergency:
                    months_covered = emergency["months_covered"]
                    if months_covered >= 6:
                        cushion_color, cushion_note = theme.var("green"), "Colchao confortavel"
                    elif months_covered >= 3:
                        cushion_color, cushion_note = theme.var("amber"), "Da para respirar"
                    else:
                        cushion_color, cushion_note = theme.var("red"), "Colchao curto"
                    components.kpi_card(
                        "Reserva de emergencia",
                        f"{months_covered:.1f} meses",
                        sub=f"Gasto medio {format_brl(emergency['average_expense_cents'])}/mes",
                        value_color=cushion_color,
                        delta_text=cushion_note,
                        delta_color=cushion_color,
                        help_text=(
                            "Quanto tempo o dinheiro que voce alcanca rapido (conta corrente e "
                            "poupanca) cobre seu gasto medio, se a receita parasse hoje. Imovel e "
                            "investimento travado nao entram: nao pagam o mercado do mes que vem."
                        ),
                    )
                if period_savings_rate is not None:
                    components.kpi_card(
                        f"Taxa de poupanca · {period_label}",
                        f"{period_savings_rate * 100:.0f}%",
                        sub="Da receita do periodo que nao virou gasto",
                        value_color=(
                            theme.var("green") if period_savings_rate >= 0.2 else theme.var("amber")
                        ),
                        help_text="Receitas menos despesas, dividido pelas receitas do periodo.",
                    )
                if sheet["liabilities_cents"] > 0 and sheet["assets_cents"] > 0:
                    ratio = sheet["liabilities_cents"] / sheet["assets_cents"]
                    components.kpi_card(
                        "Dividas sobre ativos",
                        f"{ratio * 100:.0f}%",
                        sub=f"{format_brl(sheet['liabilities_cents'])} em dividas",
                        value_color=theme.var("green") if ratio < 0.5 else theme.var("amber"),
                        help_text="Total de dividas dividido pelo total de ativos.",
                    )
                if worst_category:
                    category = worst_category["category"]
                    over = worst_category["spent_cents"] - worst_category["budget_cents"]
                    components.kpi_card(
                        "Categoria em maior desvio",
                        category.name,
                        sub=(
                            f"{format_brl(worst_category['spent_cents'])} de "
                            f"{format_brl(worst_category['budget_cents'])}"
                        ),
                        value_color=(
                            theme.var("red") if over > 0 else theme.var("amber")
                        ),
                        delta_text=(
                            f"{format_brl(over)} acima do limite"
                            if over > 0
                            else f"{worst_category['pct'] * 100:.0f}% do limite usado"
                        ),
                        delta_color=theme.var("red") if over > 0 else theme.var("amber"),
                        help_text="A categoria mais proxima de estourar (ou ja estourada) neste ciclo.",
                    )

            chart_months = max(6, period_months)

            with components.panel_grid():
                with components.card():
                    components.section_label(
                        "Evolucao do patrimonio",
                        help_text="Baseado nos snapshots que voce registra manualmente na tela Patrimonio.",
                    )
                    ui.plotly(net_worth_figure(height=180, months=chart_months)).style(
                        "width:100%;height:180px"
                    )

                with components.card():
                    components.section_label(
                        "Receitas vs. despesas por mes",
                        help_text="Ciclos cobertos pelo periodo selecionado, ancorados no mes em exibicao.",
                    )
                    ui.plotly(
                        monthly_comparison_figure(
                            month, cycle_start_day, height=180, months=chart_months
                        )
                    ).style("width:100%;height:180px")

            with components.panel_grid():
                _upcoming_payments_section(session)

                with components.card():
                    components.section_label("Metas em andamento")
                    goal_list = goals.list_goals(session)[:3]
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
                        components.progress_track(
                            pct, theme.var("accent"),
                            marker_pct=goals.expected_progress_pct(goal),
                        )

            sankey = sankey_figure(
                month, cycle_start_day, height=260, start=start, end=end
            )
            if sankey is not None:
                with components.card():
                    components.section_label(
                        f"Para onde foi o dinheiro · {period_label}",
                        help_text="Receita ate a conta, e da conta ate despesas, transferencias e sobra.",
                    )
                    ui.plotly(sankey).style("width:100%;height:260px")

            with components.card():
                components.section_label(f"Lancamentos · {period_label}")
                recent = transactions.list_transactions(
                    session, start=start, end=end, limit=10
                )
                if not recent:
                    components.empty_state("Nenhum lancamento no periodo", icon="receipt_long")
                for tx in recent:
                    _transaction_row(session, tx)

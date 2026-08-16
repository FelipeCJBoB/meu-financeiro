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
from app.ui import charts, components
from app.ui.charts import (
    cashflow_trend_figure,
    category_trend_figure,
    monthly_comparison_figure,
    net_worth_figure,
    sankey_figure,
    savings_rate_trend_figure,
)
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
                theme.category_color(category) if category else theme.current()["textm"],
            )
            sub = category.name if category else "Sem categoria"

        with ui.column().style("flex:1;gap:0"):
            ui.label(tx.description).style(f"font-size:15px;color:{theme.var('text')}")
            ui.label(f"{tx.date.strftime('%d/%m')} · {sub}").style(
                f"font-size:13px;color:{theme.var('textm')}"
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
        ui.label(f"{sign}{format_brl(shown_cents)}").style(f"font-size:15px;color:{color}")


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
                f"font-size:16px;font-weight:500;color:{theme.var('text')}"
            )

        if status["available_negative"]:
            ui.label(
                "As contas deste ciclo somam mais do que a receita - isso e um "
                "compromisso real, nao da para simplesmente adiar."
            ).style(f"font-size:15px;color:{theme.var('text2')}")

        if status.get("goals_behind"):
            ui.label(
                "O ritmo das suas metas pede mais do que sobra depois das contas "
                "este mes. A meta e sua, nao uma divida - reduzir o aporte ou "
                "empurrar o prazo em Metas resolve, sem problema nenhum."
            ).style(f"font-size:15px;color:{theme.var('text2')}")

        for rule in status["overdue_rules"]:
            with ui.row().style(
                f"width:100%;align-items:center;gap:10px;padding:6px 0;"
                f"border-top:0.5px solid {theme.var('border')}"
            ):
                with ui.column().style("flex:1;gap:0"):
                    ui.label(f"Vencida: {rule.description}").style(
                        f"font-size:15px;color:{theme.var('text')}"
                    )
                    ui.label(
                        f"Venceu em {rule.next_due_date.strftime('%d/%m/%Y')} · {format_brl(rule.amount_cents)}"
                    ).style(f"font-size:13px;color:{theme.var('textm')}")
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
                ).style(f"font-size:15px;color:{theme.var('text2')};flex:1")


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
                    ui.label(rule.description).style(f"font-size:15px;color:{theme.var('text')}")
                    account_name = account.name if account else ""
                    ui.label(
                        f"em {rule.next_due_date.strftime('%d/%m')} · {account_name}"
                    ).style(f"font-size:13px;color:{theme.var('textm')}")
                color = theme.var("green") if rule.type == TransactionType.income else theme.var("text2")
                sign = "+" if rule.type == TransactionType.income else "-"
                ui.label(f"{sign}{format_brl(rule.amount_cents)}").style(
                    f"font-size:15px;color:{color}"
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

            selected_account_id = state.account_id()
            selected_account = (
                session.get(Account, selected_account_id) if selected_account_id else None
            )
            is_combined = selected_account is None

            start, end = period_bounds(period, month, cycle_start_day)
            totals = transactions.range_totals(
                session, start, end, account_id=selected_account_id
            )
            cash_flow = totals["income_cents"] - totals["expense_cents"]

            sheet = networth.balance_sheet(session)
            total_net_worth = (
                sheet["net_worth_cents"]
                if is_combined
                else accounts.account_balance_cents(session, selected_account_id)
            )
            summary = budgets.month_summary(session, month, cycle_start_day)
            budget_pct = (
                summary["spent_cents"] / summary["budget_cents"] if summary["budget_cents"] else 0.0
            )

            prev_start, prev_end = period_bounds(
                period, previous_month(month), cycle_start_day
            )
            prev_totals = transactions.range_totals(
                session, prev_start, prev_end, account_id=selected_account_id
            )
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

            # These only make sense across every account: a budget is by category,
            # a goal is not tied to one account, and an emergency cushion is your
            # total reachable money. Slicing them per account would be meaningless.
            pace = budgets.spend_pace(session, month, cycle_start_day) if is_combined else None
            available = (
                planning.available_to_spend(session, month, cycle_start_day)
                if is_combined
                else None
            )
            allowance = (
                planning.daily_allowance(session, month, cycle_start_day)
                if is_combined
                else None
            )
            status = planning.overall_status(session, month, cycle_start_day)
            emergency = (
                planning.emergency_fund_months(session, month, cycle_start_day)
                if is_combined
                else None
            )
            period_savings_rate = planning.savings_rate(
                session, start, end, account_id=selected_account_id
            )
            worst_category = (
                planning.worst_budget_category(session, month, cycle_start_day)
                if is_combined
                else None
            )
            trend_points = networth.trend(session, months=2) if is_combined else []
            sparkline_trend = networth.trend(session, months=7) if is_combined else []

            with ui.row().style(
                "width:100%;justify-content:space-between;align-items:center;"
                "flex-wrap:wrap;gap:8px"
            ):
                with ui.row().style("align-items:center;gap:8px;flex-wrap:wrap"):
                    components.period_selector()
                    components.account_filter_selector()
                if is_month_view:
                    components.month_navigator()
                else:
                    ui.label(
                        f"{start.strftime('%d/%m/%Y')} até {end.strftime('%d/%m/%Y')}"
                    ).style(f"font-size:15px;color:{theme.var('text2')}")

            if not is_combined:
                with ui.row().style(
                    f"width:100%;align-items:center;gap:8px;padding:8px 12px;"
                    f"border-radius:8px;background:{theme.rgba(theme.current()['accent2'], 0.10)}"
                ):
                    ui.icon("filter_alt").style(
                        f"color:{theme.var('accent2')};font-size:16px"
                    )
                    ui.label(
                        f"Vendo apenas {selected_account.name}. Orcamento, metas, reserva de "
                        f"emergencia e dividas sao calculados sobre todas as contas juntas, "
                        f"entao ficam ocultos aqui."
                    ).style(f"font-size:14px;color:{theme.var('text2')}")

            if is_combined:
                _exception_banner(session, status, lambda: ui.navigate.reload())

            # T1 - hero: the one number this whole screen exists to answer. It sits
            # unboxed above every card, roughly 1.6x a KPI card's size, so it reads
            # as the headline instead of one card among ten equals - see design.py.
            previous_net_worth = trend_points[0][1] if len(trend_points) > 1 else None
            if previous_net_worth:
                nw_delta = total_net_worth - previous_net_worth
                nw_arrow = "▲" if nw_delta >= 0 else "▼"
                nw_delta_text = (
                    f"{nw_arrow} {format_brl(abs(nw_delta))} "
                    f"({abs(nw_delta) / abs(previous_net_worth) * 100:.1f}%) vs mes anterior"
                )
                nw_delta_color = theme.var("green") if nw_delta >= 0 else theme.var("red")
            else:
                nw_delta_text, nw_delta_color = "", None

            components.hero_metric(
                "Patrimonio liquido" if is_combined else f"Saldo · {selected_account.name}",
                format_brl(total_net_worth),
                delta_text=nw_delta_text,
                delta_color=nw_delta_color,
                sparkline_points=(
                    [v / 100 for _, v in sparkline_trend] if len(sparkline_trend) > 1 else None
                ),
                sparkline_color=nw_delta_color or theme.var("text2"),
                help_text=(
                    "Tudo que voce tem menos tudo que voce deve."
                    if is_combined
                    else "Saldo calculado desta conta: saldo inicial mais tudo que entrou e saiu dela."
                ),
                on_click=lambda: ui.navigate.to("/patrimonio"),
            )

            free = available["available_cents"] if available else None
            allowance_text = (
                f"{format_brl(allowance['per_day_cents'])}/dia nos {allowance['days_remaining']} dias restantes"
                if allowance
                else ""
            )
            goals_need_cents = available["goals_need_cents"] if available else 0
            goals_in_t2 = goals_need_cents > 0
            free_after_goals = (free - goals_need_cents) if free is not None else 0

            # The pace/budget card is a single slot either way: spend-pace projection
            # and the plain budget percentage never make sense on screen together,
            # so only one of them ever exists at a time.
            pace_label = pace_value = pace_sub = pace_color = None
            pace_delta = pace_delta_color = pace_help = None
            if pace:
                over = pace["over_by_cents"]
                pace_label = "Ritmo de gasto"
                pace_value = format_brl(pace["projected_cents"])
                pace_sub = f"Projetado p/ fim do mes (dia {pace['days_elapsed']} de {pace['days_in_month']})"
                pace_color = theme.var("red") if over > 0 else theme.var("green")
                pace_delta = f"{'Acima' if over > 0 else 'Dentro'} do orcamento em {format_brl(abs(over))}"
                pace_delta_color = pace_color
                pace_help = (
                    "Projecao linear: gasto ate hoje dividido pelos dias decorridos, "
                    "multiplicado pelos dias do ciclo. Assume que voce vai continuar "
                    "gastando no mesmo ritmo ate o fim do mes."
                )
            elif is_combined:
                pace_label = "Orcamento do mes"
                pace_value = f"{budget_pct * 100:.0f}%" if summary["budget_cents"] else "--"
                pace_sub = (
                    f"{format_brl(summary['spent_cents'])} de {format_brl(summary['budget_cents'])}"
                    if summary["budget_cents"]
                    else "Nenhum orcamento definido"
                )
                pace_help = "Percentual do total orcado nas categorias que ja foi gasto neste ciclo."

            # T2 - decision: at most three cards, the numbers that change what you do
            # today. Metas keeps its own dedicated card whenever it applies - Ritmo/
            # Orcamento is what steps aside for it, folding into the T3 strip below,
            # since it overlaps conceptually with Fluxo (both read "how is this
            # month trending") in a way Metas does not.
            with components.kpi_grid():
                if free is not None:
                    components.kpi_card(
                        "Disponivel para gastar",
                        format_brl(free),
                        sub=(
                            f"Receita {format_brl(available['income_total_cents'])} - "
                            f"compromissos {format_brl(available['bills_cents'])}"
                        ),
                        value_color=components.money_color(free),
                        glow=theme.current()["glow_pos" if free >= 0 else "glow_neg"],
                        delta_text=allowance_text,
                        help_text=(
                            "Receita recebida + recorrencias de entrada ainda a vencer, menos "
                            "despesas ja pagas e contas fixas a vencer neste ciclo. Metas nao "
                            "entram nessa conta - elas tem card proprio ao lado, porque meta e "
                            "um objetivo que voce escolheu, nao um compromisso como uma conta. "
                            "O segundo valor divide o total pelos dias que faltam no ciclo."
                        ),
                        on_click=lambda: ui.navigate.to("/orcamento"),
                    )
                components.kpi_card(
                    f"Fluxo · {period_label}",
                    format_brl(cash_flow),
                    sub=f"Receitas {format_brl(totals['income_cents'])} · Despesas {format_brl(totals['expense_cents'])}",
                    value_color=components.money_color(cash_flow),
                    glow=theme.current()['glow_pos' if cash_flow >= 0 else 'glow_neg'],
                    delta_text=delta_text,
                    delta_color=delta_color,
                    help_text=(
                        "Receitas menos despesas lancadas no periodo selecionado "
                        "(nao inclui recorrencias futuras)."
                    ),
                    on_click=lambda: ui.navigate.to("/lancamentos"),
                )
                if goals_in_t2:
                    goals_covered = free_after_goals >= 0
                    components.kpi_card(
                        "Metas do mes",
                        format_brl(goals_need_cents),
                        sub=f"Livre depois das contas: {format_brl(free)}",
                        delta_text=(
                            "Cabe dentro do que sobra depois das contas"
                            if goals_covered
                            else f"Faltam {format_brl(abs(free_after_goals))} para cobrir o ritmo deste mes"
                        ),
                        delta_color=theme.var("pos") if goals_covered else theme.var("amber"),
                        help_text=(
                            "Soma do quanto cada meta com prazo precisa receber este mes para "
                            "chegar no valor combinado na data combinada. Nao e uma cobranca: "
                            "se nao couber no que sobra depois das contas, o ritmo da meta e "
                            "que pode ceder - ajuste o aporte ou o prazo em Metas."
                        ),
                        on_click=lambda: ui.navigate.to("/metas"),
                    )
                elif pace_label:
                    components.kpi_card(
                        pace_label,
                        pace_value,
                        sub=pace_sub,
                        value_color=pace_color,
                        delta_text=pace_delta,
                        delta_color=pace_delta_color,
                        help_text=pace_help,
                        on_click=lambda: ui.navigate.to("/orcamento"),
                    )

            # T3 - diagnostic: compact, no card weight, one glance to confirm nothing
            # here needs attention right now.
            stat_items = []
            if goals_in_t2 and pace_label:
                stat_items.append(
                    {
                        "label": pace_label,
                        "value": pace_value,
                        "note": pace_delta,
                        "value_color": pace_color,
                        "note_color": pace_delta_color,
                        "help_text": pace_help,
                    }
                )
            if emergency:
                months_covered = emergency["months_covered"]
                if months_covered >= 6:
                    cushion_color, cushion_note = theme.var("green"), "Colchao confortavel"
                elif months_covered >= 3:
                    cushion_color, cushion_note = theme.var("amber"), "Da para respirar"
                else:
                    cushion_color, cushion_note = theme.var("red"), "Colchao curto"
                stat_items.append(
                    {
                        "label": "Reserva de emergencia",
                        "value": f"{months_covered:.1f} meses",
                        "note": cushion_note,
                        "value_color": cushion_color,
                        "note_color": cushion_color,
                        "help_text": (
                            "Quanto tempo o dinheiro que voce alcanca rapido (conta corrente e "
                            "poupanca) cobre seu gasto medio, se a receita parasse hoje. Imovel e "
                            "investimento travado nao entram: nao pagam o mercado do mes que vem."
                        ),
                    }
                )
            if period_savings_rate is not None:
                stat_items.append(
                    {
                        "label": f"Taxa de poupanca · {period_label}",
                        "value": f"{period_savings_rate * 100:.0f}%",
                        "note": "Da receita do periodo que nao virou gasto",
                        "value_color": (
                            theme.var("green") if period_savings_rate >= 0.2 else theme.var("amber")
                        ),
                        "help_text": "Receitas menos despesas, dividido pelas receitas do periodo.",
                    }
                )
            if is_combined and sheet["liabilities_cents"] > 0 and sheet["assets_cents"] > 0:
                ratio = sheet["liabilities_cents"] / sheet["assets_cents"]
                stat_items.append(
                    {
                        "label": "Dividas sobre ativos",
                        "value": f"{ratio * 100:.0f}%",
                        "note": f"{format_brl(sheet['liabilities_cents'])} em dividas",
                        "value_color": theme.var("green") if ratio < 0.5 else theme.var("amber"),
                        "help_text": "Total de dividas dividido pelo total de ativos.",
                    }
                )
            if worst_category:
                category = worst_category["category"]
                over = worst_category["spent_cents"] - worst_category["budget_cents"]
                stat_items.append(
                    {
                        "label": "Categoria em maior desvio",
                        "value": category.name,
                        "note": (
                            f"{format_brl(over)} acima do limite"
                            if over > 0
                            else f"{worst_category['pct'] * 100:.0f}% do limite usado"
                        ),
                        "value_color": theme.var("red") if over > 0 else theme.var("amber"),
                        "note_color": theme.var("red") if over > 0 else theme.var("amber"),
                        "help_text": "A categoria mais proxima de estourar (ou ja estourada) neste ciclo.",
                    }
                )
            components.stat_strip(stat_items)

            chart_months = max(6, period_months)

            if is_combined:
                with components.panel_grid():
                    with components.card():
                        components.section_label(
                            "Evolucao do patrimonio",
                            help_text=(
                                "Uma foto do seu patrimonio por mes, salva automaticamente no "
                                "primeiro acesso de cada mes."
                            ),
                        )
                        charts.plot(net_worth_figure(height=180, months=chart_months), height=180)

                    with components.card():
                        components.section_label(
                            "Receitas vs. despesas por mes",
                            help_text="Ciclos cobertos pelo periodo selecionado, ancorados no mes em exibicao.",
                        )
                        charts.plot(
                            monthly_comparison_figure(
                                month, cycle_start_day, height=180, months=chart_months
                            ),
                            height=180,
                        )

                history_months = max(12, chart_months)
                with components.panel_grid():
                    with components.card():
                        components.section_label(
                            "Resultado de cada mes",
                            help_text=(
                                "Receitas menos despesas, ciclo a ciclo. Barra para cima "
                                "sobrou dinheiro, para baixo o mes fechou no vermelho."
                            ),
                        )
                        charts.plot(
                            cashflow_trend_figure(
                                month, cycle_start_day, height=200, months=history_months
                            ),
                            height=200,
                        )

                    with components.card():
                        components.section_label(
                            "Taxa de poupanca ao longo do tempo",
                            help_text=(
                                "Quanto da receita sobrou em cada ciclo. A linha tracejada "
                                "marca 20%, referencia comum de disciplina financeira."
                            ),
                        )
                        charts.plot(
                            savings_rate_trend_figure(
                                month, cycle_start_day, height=200, months=history_months
                            ),
                            height=200,
                        )

                category_trend = category_trend_figure(
                    month, cycle_start_day, height=240, months=max(6, chart_months)
                )
                if category_trend is not None:
                    with components.card():
                        components.section_label(
                            "Gastos por categoria, mes a mes",
                            help_text=(
                                "Barras empilhadas das categorias que mais pesam. Serve para "
                                "achar a categoria que cresceu sem voce perceber."
                            ),
                        )
                        charts.plot(category_trend, height=240)

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
                                "font-size:15px;margin-bottom:4px"
                            ):
                                ui.label(goal.name).style(f"color:{theme.var('text')}")
                                ui.label(f"{pct * 100:.0f}%").style(
                                    f"color:{theme.var('text2')}"
                                )
                            components.progress_track(
                                pct, theme.var("accent"),
                                marker_pct=goals.expected_progress_pct(goal),
                            )

            sankey = sankey_figure(
                month,
                cycle_start_day,
                height=260,
                start=start,
                end=end,
                account_id=selected_account_id,
            )
            if sankey is not None:
                with components.card():
                    components.section_label(
                        f"Para onde foi o dinheiro · {period_label}",
                        help_text="Receita ate a conta, e da conta ate despesas, transferencias e sobra.",
                    )
                    charts.plot(sankey, height=260)

            with components.card():
                components.section_label(f"Lancamentos · {period_label}")
                recent = transactions.list_transactions(
                    session,
                    start=start,
                    end=end,
                    limit=10,
                    account_id=selected_account_id,
                )
                if not recent:
                    components.empty_state("Nenhum lancamento no periodo", icon="receipt_long")
                for tx in recent:
                    _transaction_row(session, tx)

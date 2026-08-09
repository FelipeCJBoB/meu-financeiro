from __future__ import annotations

from nicegui import ui

from app import theme
from app.db import get_session
from app.models import AccountType
from app.services import accounts as accounts_service
from app.services import forecast as forecast_service
from app.services import networth as networth_service
from app.services.money import format_brl, to_cents
from app.ui import components
from app.ui.charts import composition_donut_figure, forecast_figure, net_worth_figure
from app.ui.layout import page_frame

HORIZON_LABELS = {30: "30 dias", 60: "60 dias", 90: "90 dias"}

ACCOUNT_TYPE_LABELS = {
    AccountType.checking: "Conta corrente",
    AccountType.savings: "Poupanca / reserva",
    AccountType.credit_card: "Cartao de credito",
    AccountType.investment: "Investimento",
    AccountType.physical_asset: "Bem fisico",
    AccountType.loan: "Emprestimo / financiamento",
    AccountType.other: "Outro",
}

ACCOUNT_TYPE_ICON = {
    AccountType.checking: "account_balance",
    AccountType.savings: "savings",
    AccountType.credit_card: "credit_card",
    AccountType.investment: "trending_up",
    AccountType.physical_asset: "home",
    AccountType.loan: "request_quote",
    AccountType.other: "folder",
}


def _adjust_balance_dialog(account, on_saved) -> ui.dialog:
    with get_session() as session:
        current = accounts_service.account_balance_cents(session, account.id)

    with ui.dialog() as dialog, components.card(padding="1.25rem"):
        ui.label(f"Ajustar saldo · {account.name}").style(
            f"font-size:15px;font-weight:500;color:{theme.var('text')}"
        )
        ui.label(f"Saldo atual calculado: {format_brl(current)}").style(
            f"font-size:14px;color:{theme.var('textm')};margin-bottom:8px"
        )
        new_value_input = ui.number("Novo saldo (R$)", value=current / 100, format="%.2f").props(
            "outlined dense"
        ).style("width:100%")

        def _save() -> None:
            with get_session() as session2:
                accounts_service.adjust_balance(
                    session2, account.id, to_cents(new_value_input.value or 0)
                )
            dialog.close()
            on_saved()

        with ui.row().style("justify-content:flex-end;gap:8px;margin-top:12px;width:100%"):
            ui.button("Cancelar", on_click=dialog.close).props("flat no-caps").style(
                f"color:{theme.var('text2')}"
            )
            ui.button("Salvar", on_click=_save).props("no-caps unelevated").style(
                f"background:{theme.var('accent')};color:{theme.var('s1')}"
            )
    return dialog


def _account_row(row) -> None:
    account = row["account"]
    with ui.row().style(
        f"width:100%;align-items:center;gap:10px;padding:9px 0;"
        f"border-bottom:0.5px solid {theme.var('border')}"
    ):
        components.category_chip(
            ACCOUNT_TYPE_ICON.get(account.type, "folder"), theme.current()["accent"]
        )
        with ui.column().style("flex:1;gap:0"):
            ui.label(account.name).style(f"font-size:15px;color:{theme.var('text')}")
            ui.label(ACCOUNT_TYPE_LABELS.get(account.type, "")).style(
                f"font-size:15px;color:{theme.var('textm')}"
            )
        ui.label(format_brl(row["balance_cents"])).style(
            f"font-size:15px;color:{theme.var('text')};margin-right:8px"
        )
        adjust = _adjust_balance_dialog(account, lambda: ui.navigate.reload())
        ui.button(icon="tune", on_click=adjust.open).props("flat dense round").style(
            f"color:{theme.var('text2')}"
        ).tooltip("Ajustar saldo")
        manage = components.manage_account_dialog(account, lambda: ui.navigate.reload())
        ui.button(icon="settings", on_click=manage.open).props("flat dense round").style(
            f"color:{theme.var('text2')}"
        ).tooltip("Renomear, arquivar ou excluir")


@ui.refreshable
def _forecast_section(horizon_days: int) -> None:
    with get_session() as session:
        series = forecast_service.project_net_worth(session, horizon_days=horizon_days)
    projected_cents = series[-1][1] if series else 0

    with components.card():
        with ui.row().style("width:100%;justify-content:space-between;align-items:center"):
            components.section_label(f"Projeção de saldo · próximos {horizon_days} dias")
            ui.label(format_brl(projected_cents)).style(
                f"font-size:16px;font-weight:500;color:{theme.var('text')}"
            )
        ui.label(
            "A linha soma suas recorrências ativas ao saldo atual - não tenta prever gastos "
            "avulsos. A faixa ao redor reflete a variação real das suas despesas nos últimos "
            "meses (mais larga quanto mais longe no tempo); não é uma garantia estatística."
        ).style(f"font-size:15px;color:{theme.var('textm')};margin-bottom:8px")
        ui.plotly(forecast_figure(height=200, horizon_days=horizon_days)).style(
            "width:100%;height:200px"
        )


@ui.refreshable
def _evolution_section(months: int) -> None:
    with components.card():
        components.section_label(
            "Evolução do patrimônio líquido",
            help_text=(
                "Um ponto por snapshot registrado. Barras mostram quanto veio de aporte "
                "(dinheiro que voce colocou) e quanto veio de ganho/perda de valor."
            ),
        )
        ui.plotly(net_worth_figure(height=240, months=months)).style("width:100%;height:240px")


def _account_list(rows, *, title: str, help_text: str, empty: str) -> None:
    with components.card():
        components.section_label(title, help_text=help_text)
        if not rows:
            components.empty_state(empty, icon="account_balance_wallet")
        for row in rows:
            _account_row(row)


def render() -> None:
    with page_frame("/patrimonio"):
        with get_session() as session:
            sheet = networth_service.balance_sheet(session)
            indicators = networth_service.health_indicators(session)
            committed = networth_service.committed_to_goals_cents(session)
            trend_points = networth_service.trend(session, months=2)

        net_worth = sheet["net_worth_cents"]
        previous_net_worth = trend_points[0][1] if len(trend_points) > 1 else None
        if previous_net_worth is not None and previous_net_worth != 0:
            delta = net_worth - previous_net_worth
            arrow = "▲" if delta >= 0 else "▼"
            delta_text = (
                f"{arrow} {format_brl(abs(delta))} "
                f"({abs(delta) / abs(previous_net_worth) * 100:.1f}%) vs snapshot anterior"
            )
            delta_color = theme.var("green") if delta >= 0 else theme.var("red")
        else:
            delta_text, delta_color = "", None

        free_cents = max(0, sheet["liquid_cents"] - committed)

        with ui.row().style(
            "width:100%;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px"
        ):
            components.section_label("Patrimônio")
            with ui.row().style("gap:8px"):
                def _snapshot() -> None:
                    with get_session() as session2:
                        networth_service.create_snapshot(session2)
                    ui.navigate.reload()

                ui.button("Registrar snapshot", icon="camera", on_click=_snapshot).props(
                    "flat no-caps dense"
                ).style(f"color:{theme.var('text2')}").tooltip(
                    "Salva uma foto do patrimonio de hoje, usada no grafico de evolucao"
                )

                account_dialog = components.new_account_dialog(lambda: ui.navigate.reload())
                ui.button("Nova conta", icon="add", on_click=account_dialog.open).props(
                    "no-caps unelevated"
                ).style(f"background:{theme.var('accent')};color:{theme.var('s1')}")

        with components.kpi_grid():
            components.kpi_card(
                "Patrimonio liquido",
                format_brl(net_worth),
                sub=f"Ativos {format_brl(sheet['assets_cents'])} - dividas {format_brl(sheet['liabilities_cents'])}",
                delta_text=delta_text,
                delta_color=delta_color,
                help_text="Tudo que voce tem menos tudo que voce deve.",
            )
            components.kpi_card(
                "Disponivel de imediato",
                format_brl(sheet["liquid_cents"]),
                sub=f"{format_brl(sheet['illiquid_cents'])} em ativos menos liquidos",
                help_text=(
                    "Soma das contas correntes e poupancas - o que voce consegue acessar "
                    "rapidamente numa emergencia. Investimentos e bens fisicos ficam de fora."
                ),
            )
            components.kpi_card(
                "Livre vs. comprometido",
                format_brl(free_cents),
                sub=f"{format_brl(committed)} ja reservado para metas",
                help_text=(
                    "Do dinheiro disponivel de imediato, quanto ainda nao esta prometido "
                    "para nenhuma meta em andamento."
                ),
            )
            if indicators["debt_ratio"] is not None:
                ratio = indicators["debt_ratio"]
                components.kpi_card(
                    "Dividas sobre ativos",
                    f"{ratio * 100:.0f}%",
                    sub=(
                        "Quanto menor, mais folga"
                        if ratio < 0.5
                        else "Parcela relevante do que voce tem esta comprometida"
                    ),
                    value_color=theme.var("green") if ratio < 0.5 else theme.var("amber"),
                    help_text="Total de dividas dividido pelo total de ativos.",
                )

        with ui.row().style("width:100%;gap:6px;align-items:center"):
            ui.label("Periodo do grafico").style(
                f"font-size:14px;color:{theme.var('textm')};margin-right:4px"
            )
            for months, label in {6: "6 meses", 12: "12 meses", 60: "Tudo"}.items():
                ui.button(
                    label, on_click=lambda m=months: _evolution_section.refresh(m)
                ).props("flat dense no-caps").style(f"color:{theme.var('text2')}")
        _evolution_section(12)

        with ui.row().style("width:100%;gap:6px;align-items:center"):
            ui.label("Horizonte da projecao").style(
                f"font-size:14px;color:{theme.var('textm')};margin-right:4px"
            )
            for days, label in HORIZON_LABELS.items():
                ui.button(
                    label, on_click=lambda d=days: _forecast_section.refresh(d)
                ).props("flat dense no-caps").style(f"color:{theme.var('text2')}")
        _forecast_section(30)

        with components.panel_grid():
            _account_list(
                sheet["assets"],
                title=f"Ativos · {format_brl(sheet['assets_cents'])}",
                help_text="Tudo que voce possui: contas, investimentos e bens fisicos.",
                empty="Nenhum ativo cadastrado",
            )
            _account_list(
                sheet["liabilities"],
                title=f"Dividas · {format_brl(sheet['liabilities_cents'])}",
                help_text=(
                    "Cartoes de credito, emprestimos e financiamentos. Sao mostrados como "
                    "valor positivo aqui, mas subtraem do patrimonio liquido."
                ),
                empty="Nenhuma divida cadastrada",
            )

        if sheet["assets"]:
            with components.card():
                components.section_label(
                    "Distribuição dos ativos",
                    help_text="Proporcao do que voce possui em cada conta. Dividas nao entram aqui.",
                )
                ui.plotly(composition_donut_figure(height=240)).style("width:100%")

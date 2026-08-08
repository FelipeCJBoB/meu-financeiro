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
from app.ui.charts import forecast_figure, net_worth_figure
from app.ui.layout import page_frame

HORIZON_LABELS = {30: "30 dias", 60: "60 dias", 90: "90 dias"}

ACCOUNT_TYPE_ICON = {
    AccountType.checking: "account_balance",
    AccountType.savings: "savings",
    AccountType.credit_card: "credit_card",
    AccountType.investment: "trending_up",
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
            f"font-size:12px;color:{theme.var('textm')};margin-bottom:8px"
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
            ui.label(account.name).style(f"font-size:13px;color:{theme.var('text')}")
        ui.label(format_brl(row["balance_cents"])).style(
            f"font-size:13px;color:{theme.var('text')};margin-right:8px"
        )
        dialog = _adjust_balance_dialog(account, lambda: ui.navigate.reload())
        ui.button(icon="tune", on_click=dialog.open).props("flat dense round").style(
            f"color:{theme.var('text2')}"
        )


@ui.refreshable
def _forecast_section(horizon_days: int) -> None:
    with get_session() as session:
        series = forecast_service.project_net_worth(session, horizon_days=horizon_days)
    projected_cents = series[-1][1] if series else 0

    with components.card():
        with ui.row().style("width:100%;justify-content:space-between;align-items:center"):
            components.section_label(f"Projeção de saldo · próximos {horizon_days} dias")
            ui.label(format_brl(projected_cents)).style(
                f"font-size:14px;font-weight:500;color:{theme.var('text')}"
            )
        ui.label(
            "Baseada apenas nas suas recorrências ativas (contas fixas e receitas agendadas) "
            "somadas ao saldo atual. Nao tenta prever gastos avulsos."
        ).style(f"font-size:11px;color:{theme.var('textm')};margin-bottom:8px")
        ui.plotly(forecast_figure(height=200, horizon_days=horizon_days)).style(
            "width:100%;height:200px"
        )


def render() -> None:
    with page_frame("/patrimonio"):
        with get_session() as session:
            total, _ = networth_service.current_net_worth(session)
            composition = networth_service.composition(session)

        with ui.row().style("width:100%;justify-content:space-between;align-items:center"):
            ui.label(f"Patrimônio total · {format_brl(total)}").style(
                f"font-size:13px;color:{theme.var('text2')}"
            )
            with ui.row().style("gap:8px"):
                def _snapshot() -> None:
                    with get_session() as session2:
                        networth_service.create_snapshot(session2)
                    ui.navigate.reload()

                ui.button("Registrar snapshot", icon="camera", on_click=_snapshot).props(
                    "flat no-caps dense"
                ).style(f"color:{theme.var('text2')}")

                account_dialog = components.new_account_dialog(lambda: ui.navigate.reload())
                ui.button("Nova conta", icon="add", on_click=account_dialog.open).props(
                    "no-caps unelevated"
                ).style(f"background:{theme.var('accent')};color:{theme.var('s1')}")

        with components.card():
            components.section_label("Evolução do patrimônio líquido")
            ui.plotly(net_worth_figure(height=220, months=12)).style("width:100%;height:220px")

        with ui.row().style("width:100%;gap:6px"):
            for days, label in HORIZON_LABELS.items():
                ui.button(
                    label, on_click=lambda d=days: _forecast_section.refresh(d)
                ).props("flat dense no-caps").style(f"color:{theme.var('text2')}")
        _forecast_section(30)

        with components.card():
            components.section_label("Composição atual")
            if not composition:
                components.empty_state("Nenhuma conta cadastrada", icon="account_balance_wallet")
            for row in composition:
                _account_row(row)

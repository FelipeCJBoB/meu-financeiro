from __future__ import annotations

from typing import Callable

from nicegui import ui

from app import state, theme
from app.db import get_session
from app.models import AccountType
from app.services import accounts as accounts_service
from app.services.money import format_month_label, to_cents

ACCOUNT_TYPE_LABELS = {
    AccountType.checking.value: "Conta corrente",
    AccountType.savings.value: "Poupanca / reserva",
    AccountType.credit_card.value: "Cartao de credito",
    AccountType.investment.value: "Investimento",
    AccountType.other.value: "Outro",
}


def status_color_key(pct: float) -> str:
    if pct > 1.0:
        return "red"
    if pct >= 0.8:
        return "amber"
    return "green"


def card(*, padding: str = "1rem", grow: bool = False) -> ui.column:
    element = ui.column().style(
        f"background:{theme.var('s1')};border-radius:12px;padding:{padding};"
        f"gap:0;box-sizing:border-box;width:100%"
        + (";flex:1" if grow else "")
    )
    return element


def info_icon(text: str, *, size: str = "13px") -> None:
    icon = ui.icon("help_outline").style(
        f"font-size:{size};color:{theme.var('textm')};cursor:help;margin-left:4px"
    )
    icon.tooltip(text)


def kpi_card(
    label: str,
    value: str,
    *,
    sub: str = "",
    value_color: str | None = None,
    delta_text: str = "",
    delta_color: str | None = None,
    help_text: str = "",
) -> None:
    with card():
        with ui.row().style("align-items:center;gap:0;margin-bottom:4px"):
            ui.label(label).style(f"font-size:13px;color:{theme.var('text2')}")
            if help_text:
                info_icon(help_text)
        ui.label(value).style(
            f"font-size:22px;font-weight:500;color:{value_color or theme.var('text')}"
        )
        if sub:
            ui.label(sub).style(f"font-size:12px;color:{theme.var('textm')};margin-top:4px")
        if delta_text:
            ui.label(delta_text).style(
                f"font-size:12px;color:{delta_color or theme.var('textm')};margin-top:2px"
            )


def progress_track(pct: float, color: str, *, height: str = "6px") -> None:
    with ui.element("div").style(
        f"height:{height};background:{theme.var('border')};border-radius:4px;"
        f"overflow:hidden;width:100%"
    ):
        width = max(0.0, min(pct, 1.0)) * 100
        ui.element("div").style(f"height:100%;width:{width:.1f}%;background:{color}")


def category_chip(icon: str, color: str, *, size: str = "28px") -> ui.element:
    el = ui.icon(icon).style(
        f"width:{size};height:{size};min-width:{size};border-radius:50%;"
        f"background:{color}22;color:{color};display:flex;align-items:center;"
        f"justify-content:center;font-size:14px"
    )
    return el


def section_label(text: str, *, help_text: str = "") -> None:
    with ui.row().style("align-items:center;gap:0;margin:4px 0 4px"):
        ui.label(text).style(f"font-size:13px;color:{theme.var('text2')}")
        if help_text:
            info_icon(help_text)


def month_navigator() -> None:
    with ui.row().style("align-items:center;gap:2px"):
        def _go(delta: int) -> None:
            state.shift_month(delta)
            ui.navigate.reload()

        ui.button(icon="chevron_left", on_click=lambda: _go(-1)).props(
            "flat dense round"
        ).style(f"color:{theme.var('text2')}")

        ui.label(format_month_label(state.current_month())).style(
            f"font-size:14px;font-weight:500;color:{theme.var('text')};min-width:130px;"
            f"text-align:center"
        )

        ui.button(icon="chevron_right", on_click=lambda: _go(1)).props(
            "flat dense round"
        ).style(f"color:{theme.var('text2')}")

        if not state.is_current_cycle():
            def _today() -> None:
                state.reset_to_today()
                ui.navigate.reload()

            ui.button("Hoje", on_click=_today).props("flat dense no-caps").style(
                f"color:{theme.var('accent2')};font-size:12px"
            )


def new_account_dialog(on_created: Callable[[], None]) -> ui.dialog:
    with ui.dialog() as dialog, card(padding="1.25rem"):
        ui.label("Nova conta").style(f"font-size:15px;font-weight:500;color:{theme.var('text')}")
        name_input = ui.input("Nome da conta").props("outlined dense").style("width:100%")
        type_select = ui.select(
            dict(ACCOUNT_TYPE_LABELS),
            value=AccountType.checking.value,
            label="Tipo",
        ).props("outlined dense").style("width:100%")
        balance_input = ui.number("Saldo atual (R$)", value=0, format="%.2f").props(
            "outlined dense"
        ).style("width:100%")

        def _save() -> None:
            if not name_input.value:
                ui.notify("Informe um nome para a conta", color="negative")
                return
            with get_session() as session:
                accounts_service.create_account(
                    session,
                    name=name_input.value,
                    type=AccountType(type_select.value),
                    initial_balance_cents=to_cents(balance_input.value or 0),
                )
            dialog.close()
            on_created()

        with ui.row().style("justify-content:flex-end;gap:8px;margin-top:12px;width:100%"):
            ui.button("Cancelar", on_click=dialog.close).props("flat no-caps").style(
                f"color:{theme.var('text2')}"
            )
            ui.button("Criar conta", on_click=_save).props("no-caps unelevated").style(
                f"background:{theme.var('accent')};color:{theme.var('s1')}"
            )
    return dialog


def settings_dialog() -> ui.dialog:
    with ui.dialog() as dialog, card(padding="1.25rem"):
        ui.label("Configuracoes").style(
            f"font-size:15px;font-weight:500;color:{theme.var('text')}"
        )
        ui.label(
            "Dia do mes em que seu ciclo financeiro comeca (ex: dia do salario). "
            "Use 1 para seguir o mes calendario normal."
        ).style(f"font-size:12px;color:{theme.var('textm')};margin:6px 0 10px")

        day_input = ui.number(
            "Dia de inicio do ciclo", value=state.cycle_start_day(), min=1, max=31, format="%.0f"
        ).props("outlined dense").style("width:100%")

        def _save() -> None:
            state.set_cycle_start_day(int(day_input.value or 1))
            dialog.close()
            ui.navigate.reload()

        with ui.row().style("justify-content:flex-end;gap:8px;margin-top:14px;width:100%"):
            ui.button("Cancelar", on_click=dialog.close).props("flat no-caps").style(
                f"color:{theme.var('text2')}"
            )
            ui.button("Salvar", on_click=_save).props("no-caps unelevated").style(
                f"background:{theme.var('accent')};color:{theme.var('s1')}"
            )
    return dialog


def empty_state(text: str, *, icon: str = "inbox") -> None:
    with ui.column().style(
        f"width:100%;align-items:center;justify-content:center;padding:2rem;"
        f"color:{theme.var('textm')};gap:8px"
    ):
        ui.icon(icon).style("font-size:28px")
        ui.label(text).style("font-size:13px")

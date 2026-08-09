from __future__ import annotations

from typing import Callable

from nicegui import ui

from app import state, theme
from app.db import get_session
from app.models import AccountType
from app.services import accounts as accounts_service
from app.services.money import format_brl, format_month_label, to_cents

ACCOUNT_TYPE_LABELS = {
    AccountType.checking.value: "Conta corrente",
    AccountType.savings.value: "Poupanca / reserva",
    AccountType.investment.value: "Investimento",
    AccountType.physical_asset.value: "Bem fisico (imovel, carro)",
    AccountType.credit_card.value: "Cartao de credito (divida)",
    AccountType.loan.value: "Emprestimo / financiamento (divida)",
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


def kpi_grid(*, min_width: str = "230px") -> ui.element:
    """Auto-fitting grid so KPI cards share a row instead of each taking full width."""
    return ui.element("div").style(
        f"width:100%;display:grid;gap:12px;"
        f"grid-template-columns:repeat(auto-fit,minmax({min_width},1fr))"
    )


def panel_grid(*, min_width: str = "340px") -> ui.element:
    return ui.element("div").style(
        f"width:100%;display:grid;gap:16px;align-items:start;"
        f"grid-template-columns:repeat(auto-fit,minmax({min_width},1fr))"
    )


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


def progress_track(
    pct: float, color: str, *, height: str = "6px", marker_pct: float | None = None
) -> None:
    with ui.element("div").style(
        f"height:{height};background:{theme.var('border')};border-radius:4px;"
        f"overflow:visible;width:100%;position:relative"
    ):
        width = max(0.0, min(pct, 1.0)) * 100
        ui.element("div").style(
            f"height:100%;width:{width:.1f}%;background:{color};border-radius:4px;overflow:hidden"
        )
        if marker_pct is not None:
            marker_left = max(0.0, min(marker_pct, 1.0)) * 100
            marker = ui.element("div").style(
                f"position:absolute;top:-2px;bottom:-2px;left:{marker_left:.1f}%;"
                f"width:2px;background:{theme.var('text')};border-radius:1px"
            )
            marker.tooltip("Onde voce deveria estar hoje, no ritmo linear ate o prazo")


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


def period_selector() -> None:
    """Segmented control: the Dashboard stops being a one-month-at-a-time view."""
    from app.services.money import PERIOD_LABELS

    current = state.period()
    with ui.row().style(
        f"align-items:center;gap:0;border:0.5px solid {theme.var('border')};"
        f"border-radius:8px;overflow:hidden"
    ):
        for value, label in PERIOD_LABELS.items():
            is_active = value == current

            def _pick(value=value) -> None:
                state.set_period(value)
                ui.navigate.reload()

            btn = ui.button(label, on_click=_pick).props("flat no-caps dense square")
            btn.style(
                f"color:{theme.var('s1') if is_active else theme.var('text2')};"
                f"background:{theme.var('accent') if is_active else 'transparent'};"
                f"font-size:12px;border-radius:0;min-width:64px;"
                f"font-weight:{'500' if is_active else '400'}"
            )


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


def manage_account_dialog(account, on_saved: Callable[[], None]) -> ui.dialog:
    with get_session() as session:
        tx_count = accounts_service.transaction_count(session, account.id)

    with ui.dialog() as dialog, card(padding="1.25rem"):
        ui.label(f"Gerenciar conta · {account.name}").style(
            f"font-size:15px;font-weight:500;color:{theme.var('text')};margin-bottom:8px"
        )

        name_input = ui.input("Nome da conta", value=account.name).props(
            "outlined dense"
        ).style("width:100%")
        type_select = ui.select(
            dict(ACCOUNT_TYPE_LABELS), value=account.type.value, label="Tipo"
        ).props("outlined dense").style("width:100%")

        def _save() -> None:
            if not name_input.value:
                ui.notify("Informe um nome para a conta", color="negative")
                return
            with get_session() as session2:
                accounts_service.update_account(
                    session2,
                    account.id,
                    name=name_input.value,
                    type=AccountType(type_select.value),
                )
            dialog.close()
            on_saved()

        ui.label(
            f"{tx_count} lancamento(s) vinculado(s) a esta conta."
            if tx_count
            else "Nenhum lancamento vinculado."
        ).style(f"font-size:12px;color:{theme.var('textm')};margin-top:12px")

        ui.label(
            "Arquivar esconde a conta das telas, mas mantem o historico intacto. "
            "Excluir remove a conta e todos os lancamentos dela, sem volta."
        ).style(f"font-size:11px;color:{theme.var('textm')};margin-top:4px")

        confirm_delete = ui.checkbox(
            f"Confirmo excluir a conta e seus {tx_count} lancamento(s)"
            if tx_count
            else "Confirmo excluir esta conta"
        ).style("margin-top:8px")

        def _archive() -> None:
            with get_session() as session2:
                accounts_service.set_archived(session2, account.id, True)
            dialog.close()
            on_saved()

        def _delete() -> None:
            if not confirm_delete.value:
                ui.notify("Marque a confirmacao antes de excluir", color="negative")
                return
            with get_session() as session2:
                accounts_service.delete_account(session2, account.id, cascade=True)
            dialog.close()
            on_saved()

        with ui.row().style(
            "justify-content:space-between;gap:8px;margin-top:14px;width:100%;flex-wrap:wrap"
        ):
            with ui.row().style("gap:8px"):
                ui.button("Arquivar", icon="inventory_2", on_click=_archive).props(
                    "flat no-caps dense"
                ).style(f"color:{theme.var('text2')}")
                ui.button("Excluir", icon="delete", on_click=_delete).props(
                    "flat no-caps dense"
                ).style(f"color:{theme.var('red')}")
            with ui.row().style("gap:8px"):
                ui.button("Cancelar", on_click=dialog.close).props("flat no-caps").style(
                    f"color:{theme.var('text2')}"
                )
                ui.button("Salvar", on_click=_save).props("no-caps unelevated").style(
                    f"background:{theme.var('accent')};color:{theme.var('s1')}"
                )
    return dialog


WINDOW_PRESETS = [
    ("2K", 2560, 1440),
    ("Full HD", 1920, 1080),
]


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

        ui.label("Tamanho da janela").style(
            f"font-size:13px;color:{theme.var('text')};margin-top:16px"
        )
        ui.label(
            "Aplica na hora e vira o tamanho padrao na proxima vez que voce abrir o app."
        ).style(f"font-size:12px;color:{theme.var('textm')};margin-bottom:8px")

        with ui.row().style("gap:8px;width:100%"):
            for label, width, height in WINDOW_PRESETS:

                def _apply(width=width, height=height) -> None:
                    state.set_window_size(width, height)
                    from nicegui import app as nicegui_app

                    if nicegui_app.native.main_window:
                        nicegui_app.native.main_window.resize(width, height)
                    ui.notify(f"Janela ajustada para {width}x{height}")

                ui.button(f"{label} ({width}x{height})", on_click=_apply).props(
                    "flat no-caps dense"
                ).style(f"color:{theme.var('text2')};border:0.5px solid {theme.var('border')}")

        def _save() -> None:
            state.set_cycle_start_day(int(day_input.value or 1))
            dialog.close()
            ui.navigate.reload()

        with ui.row().style("justify-content:flex-end;gap:8px;margin-top:14px;width:100%"):
            ui.button("Fechar", on_click=dialog.close).props("flat no-caps").style(
                f"color:{theme.var('text2')}"
            )
            ui.button("Salvar ciclo", on_click=_save).props("no-caps unelevated").style(
                f"background:{theme.var('accent')};color:{theme.var('s1')}"
            )
    return dialog


def confirm_recurring_dialog(rule, on_saved: Callable[[], None]) -> ui.dialog:
    with ui.dialog() as dialog, card(padding="1.25rem"):
        ui.label(f"Confirmar: {rule.description}").style(
            f"font-size:15px;font-weight:500;color:{theme.var('text')}"
        )
        ui.label(
            f"Venceu em {rule.next_due_date.strftime('%d/%m/%Y')}. Ajuste o valor se essa "
            f"conta veio diferente do cadastrado."
        ).style(f"font-size:12px;color:{theme.var('textm')};margin:6px 0 10px")

        amount_input = ui.number(
            "Valor (R$)", value=rule.amount_cents / 100, format="%.2f"
        ).props("outlined dense").style("width:100%")

        def _save() -> None:
            from app.services import recurring as recurring_service

            with get_session() as session:
                recurring_service.confirm_recurring(
                    session, rule.id, amount_cents=to_cents(amount_input.value or 0)
                )
            dialog.close()
            on_saved()

        with ui.row().style("justify-content:flex-end;gap:8px;margin-top:14px;width:100%"):
            ui.button("Cancelar", on_click=dialog.close).props("flat no-caps").style(
                f"color:{theme.var('text2')}"
            )
            ui.button("Confirmar", on_click=_save).props("no-caps unelevated").style(
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

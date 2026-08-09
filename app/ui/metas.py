from __future__ import annotations

from datetime import date

from nicegui import ui

from app import theme
from app.db import get_session
from app.services import goals as goals_service
from app.services.money import format_brl, to_cents
from app.ui import components
from app.ui.layout import page_frame


def _new_goal_dialog(on_saved) -> ui.dialog:
    with ui.dialog() as dialog, components.card(padding="1.25rem"):
        ui.label("Nova meta").style(f"font-size:15px;font-weight:500;color:{theme.var('text')}")
        name_input = ui.input("Nome da meta").props("outlined dense").style("width:100%")
        target_input = ui.number("Valor alvo (R$)", value=0, format="%.2f").props(
            "outlined dense"
        ).style("width:100%")
        date_input = ui.input("Prazo (opcional)").props("outlined dense type=date").style(
            "width:100%"
        )

        def _save() -> None:
            if not name_input.value or not target_input.value:
                ui.notify("Informe nome e valor alvo", color="negative")
                return
            with get_session() as session:
                goals_service.create_goal(
                    session,
                    name=name_input.value,
                    target_amount_cents=to_cents(target_input.value),
                    target_date=date.fromisoformat(date_input.value) if date_input.value else None,
                )
            dialog.close()
            on_saved()

        with ui.row().style("justify-content:flex-end;gap:8px;margin-top:12px;width:100%"):
            ui.button("Cancelar", on_click=dialog.close).props("flat no-caps").style(
                f"color:{theme.var('text2')}"
            )
            ui.button("Criar meta", on_click=_save).props("no-caps unelevated").style(
                f"background:{theme.var('accent')};color:{theme.var('s1')}"
            )
    return dialog


def _contribute_dialog(goal_id: int, on_saved) -> ui.dialog:
    with ui.dialog() as dialog, components.card(padding="1.25rem"):
        ui.label("Registrar aporte").style(
            f"font-size:15px;font-weight:500;color:{theme.var('text')}"
        )
        amount_input = ui.number("Valor (R$)", value=0, format="%.2f").props(
            "outlined dense"
        ).style("width:100%")

        def _save() -> None:
            if not amount_input.value:
                return
            with get_session() as session:
                goals_service.contribute(session, goal_id, to_cents(amount_input.value))
            dialog.close()
            on_saved()

        with ui.row().style("justify-content:flex-end;gap:8px;margin-top:12px;width:100%"):
            ui.button("Cancelar", on_click=dialog.close).props("flat no-caps").style(
                f"color:{theme.var('text2')}"
            )
            ui.button("Registrar", on_click=_save).props("no-caps unelevated").style(
                f"background:{theme.var('accent')};color:{theme.var('s1')}"
            )
    return dialog


def _goal_card(goal) -> None:
    pct = goals_service.progress_pct(goal)
    with components.card():
        ui.icon(goal.icon).style(f"font-size:20px;color:{theme.var('accent')}")
        ui.label(goal.name).style(
            f"font-weight:500;font-size:14px;color:{theme.var('text')};margin:10px 0 2px"
        )
        remaining = max(0, goal.target_amount_cents - goal.current_amount_cents)
        sub = f"{format_brl(goal.current_amount_cents)} de {format_brl(goal.target_amount_cents)}"
        if goal.target_date:
            sub += f" · até {goal.target_date.strftime('%m/%Y')}"
        ui.label(sub).style(f"font-size:12px;color:{theme.var('textm')};margin-bottom:10px")
        components.progress_track(pct, theme.var("accent"))
        ui.label(f"{pct * 100:.0f}% · faltam {format_brl(remaining)}").style(
            f"font-size:12px;color:{theme.var('text2')};margin-top:6px"
        )
        dialog = _contribute_dialog(goal.id, lambda: ui.navigate.reload())
        ui.button("Registrar aporte", on_click=dialog.open).props(
            "flat dense no-caps"
        ).style(f"color:{theme.var('accent2')};font-size:12px;margin-top:8px;align-self:flex-start")


def render() -> None:
    with page_frame("/metas"):
        with ui.row().style("width:100%;justify-content:space-between;align-items:center"):
            components.section_label(
                "Metas financeiras",
                help_text="O progresso mostra o que voce ja guardou. Definir um prazo ativa o calculo de aporte mensal necessario, usado no Disponivel para gastar do Dashboard.",
            )
            dialog = _new_goal_dialog(lambda: ui.navigate.reload())
            ui.button("Nova meta", icon="add", on_click=dialog.open).props(
                "no-caps unelevated"
            ).style(f"background:{theme.var('accent')};color:{theme.var('s1')}")

        with get_session() as session:
            goal_list = goals_service.list_goals(session)

        if not goal_list:
            with components.card(padding="2rem"):
                components.empty_state("Nenhuma meta criada ainda", icon="flag")
        else:
            with ui.row().style("width:100%;gap:12px;flex-wrap:wrap"):
                for goal in goal_list:
                    with ui.column().style("flex:1;min-width:220px"):
                        _goal_card(goal)

from __future__ import annotations

from datetime import date

from nicegui import ui

from app import theme
from app.db import get_session
from app.models import GoalStatus
from app.services import goals as goals_service
from app.services.money import format_brl, to_cents
from app.ui import components
from app.ui.charts import goal_progress_figure
from app.ui.layout import page_frame

STATUS_LABELS = {
    GoalStatus.active.value: "Em andamento",
    GoalStatus.paused.value: "Pausada",
    GoalStatus.completed.value: "Concluida",
}

GOAL_ICON_OPTIONS = {
    "flag": "Bandeira",
    "savings": "Reserva",
    "flight": "Viagem",
    "home": "Casa",
    "directions_car": "Carro",
    "school": "Estudo",
    "trending_up": "Investimento",
    "credit_card": "Quitar divida",
}


def _goal_form_dialog(on_saved, *, editing=None) -> ui.dialog:
    with ui.dialog() as dialog, components.card(padding="1.25rem"):
        ui.label("Editar meta" if editing else "Nova meta").style(
            f"font-size:15px;font-weight:500;color:{theme.var('text')};margin-bottom:6px"
        )
        name_input = ui.input(
            "Nome da meta", value=editing.name if editing else ""
        ).props("outlined dense").style("width:100%")
        target_input = ui.number(
            "Valor alvo (R$)",
            value=editing.target_amount_cents / 100 if editing else 0,
            format="%.2f",
        ).props("outlined dense").style("width:100%")
        date_input = ui.input(
            "Prazo (opcional)",
            value=editing.target_date.isoformat() if editing and editing.target_date else "",
        ).props("outlined dense type=date").style("width:100%")

        with ui.row().style("width:100%;gap:8px"):
            icon_select = ui.select(
                dict(GOAL_ICON_OPTIONS),
                value=editing.icon if editing and editing.icon in GOAL_ICON_OPTIONS else "flag",
                label="Icone",
            ).props("outlined dense").style("flex:1")
            status_select = ui.select(
                dict(STATUS_LABELS),
                value=editing.status.value if editing else GoalStatus.active.value,
                label="Status",
            ).props("outlined dense").style("flex:1")
            if not editing:
                status_select.set_visibility(False)

        def _save() -> None:
            if not name_input.value or not target_input.value:
                ui.notify("Informe nome e valor alvo", color="negative")
                return
            target_date = date.fromisoformat(date_input.value) if date_input.value else None
            with get_session() as session:
                if editing:
                    goals_service.update_goal(
                        session,
                        editing.id,
                        name=name_input.value,
                        target_amount_cents=to_cents(target_input.value),
                        target_date=target_date,
                        clear_target_date=target_date is None,
                        icon=icon_select.value,
                        status=GoalStatus(status_select.value),
                    )
                else:
                    goals_service.create_goal(
                        session,
                        name=name_input.value,
                        target_amount_cents=to_cents(target_input.value),
                        target_date=target_date,
                        icon=icon_select.value,
                    )
            dialog.close()
            on_saved()

        def _delete() -> None:
            with get_session() as session:
                goals_service.delete_goal(session, editing.id)
            dialog.close()
            on_saved()

        with ui.row().style(
            "justify-content:space-between;gap:8px;margin-top:14px;width:100%;flex-wrap:wrap"
        ):
            if editing:
                ui.button("Excluir meta", icon="delete", on_click=_delete).props(
                    "flat no-caps dense"
                ).style(f"color:{theme.var('red')}")
            else:
                ui.element("div")
            with ui.row().style("gap:8px"):
                ui.button("Cancelar", on_click=dialog.close).props("flat no-caps").style(
                    f"color:{theme.var('text2')}"
                )
                ui.button(
                    "Salvar alteracoes" if editing else "Criar meta", on_click=_save
                ).props("no-caps unelevated").style(
                    f"background:{theme.var('accent')};color:{theme.var('s1')}"
                )
    return dialog


def _contributions_dialog(goal, on_saved) -> ui.dialog:
    with get_session() as session:
        history = [
            {"id": c.id, "date": c.date.strftime("%d/%m/%Y"), "amount_cents": c.amount_cents,
             "note": c.note or ""}
            for c in goals_service.list_contributions(session, goal.id)
        ]

    with ui.dialog() as dialog, components.card(padding="1.25rem"):
        ui.label(f"Aportes · {goal.name}").style(
            f"font-size:15px;font-weight:500;color:{theme.var('text')}"
        )

        amount_input = ui.number("Novo aporte (R$)", value=0, format="%.2f").props(
            "outlined dense"
        ).style("width:100%;min-width:320px")
        date_input = ui.input("Data", value=date.today().isoformat()).props(
            "outlined dense type=date"
        ).style("width:100%")

        def _add() -> None:
            if not amount_input.value:
                ui.notify("Informe um valor", color="negative")
                return
            with get_session() as session:
                goals_service.contribute(
                    session,
                    goal.id,
                    to_cents(amount_input.value),
                    on_date=date.fromisoformat(date_input.value),
                )
            dialog.close()
            on_saved()

        ui.button("Registrar aporte", on_click=_add).props("no-caps unelevated dense").style(
            f"background:{theme.var('accent')};color:{theme.var('s1')};margin-top:8px"
        )

        components.section_label("Historico")
        if not history:
            components.empty_state("Nenhum aporte registrado", icon="savings")
        for entry in history:
            with ui.row().style(
                f"width:100%;align-items:center;gap:10px;padding:7px 0;"
                f"border-bottom:0.5px solid {theme.var('border')}"
            ):
                with ui.column().style("flex:1;gap:0"):
                    ui.label(format_brl(entry["amount_cents"])).style(
                        f"font-size:15px;color:{theme.var('green')}"
                    )
                    ui.label(f"{entry['date']}{' · ' + entry['note'] if entry['note'] else ''}").style(
                        f"font-size:13px;color:{theme.var('textm')}"
                    )

                def _remove(contribution_id=entry["id"]) -> None:
                    with get_session() as session:
                        goals_service.delete_contribution(session, contribution_id)
                    dialog.close()
                    on_saved()

                ui.button(icon="delete", on_click=_remove).props("flat dense round").style(
                    f"color:{theme.var('textm')}"
                ).tooltip("Remover este aporte")

        with ui.row().style("justify-content:flex-end;margin-top:12px;width:100%"):
            ui.button("Fechar", on_click=dialog.close).props("flat no-caps").style(
                f"color:{theme.var('text2')}"
            )
    return dialog


def _goal_card(session, goal) -> None:
    pct = goals_service.progress_pct(goal)
    expected = goals_service.expected_progress_pct(goal)
    remaining = max(0, goal.target_amount_cents - goal.current_amount_cents)
    months_left = goals_service.months_to_target(session, goal)
    required = goals_service.required_monthly_cents(goal)
    is_done = goal.status == GoalStatus.completed

    with components.card():
        with ui.row().style("width:100%;align-items:center;gap:8px"):
            ui.icon(goal.icon).style(f"font-size:20px;color:{theme.var('accent')}")
            ui.label(goal.name).style(
                f"font-weight:500;font-size:14px;color:{theme.var('text')};flex:1"
            )
            badge_color = {
                GoalStatus.active: theme.var("accent2"),
                GoalStatus.paused: theme.var("textm"),
                GoalStatus.completed: theme.var("green"),
            }[goal.status]
            ui.label(STATUS_LABELS[goal.status.value]).style(
                f"font-size:15px;color:{badge_color}"
            )
            edit = _goal_form_dialog(lambda: ui.navigate.reload(), editing=goal)
            ui.button(icon="edit", on_click=edit.open).props("flat dense round").style(
                f"color:{theme.var('textm')}"
            ).tooltip("Editar meta")

        sub = f"{format_brl(goal.current_amount_cents)} de {format_brl(goal.target_amount_cents)}"
        if goal.target_date:
            sub += f" · até {goal.target_date.strftime('%m/%Y')}"
        ui.label(sub).style(f"font-size:14px;color:{theme.var('textm')};margin:6px 0 10px")

        components.progress_track(pct, theme.var("accent"), marker_pct=expected)
        ui.label(f"{pct * 100:.0f}% · faltam {format_brl(remaining)}").style(
            f"font-size:14px;color:{theme.var('text2')};margin-top:6px"
        )

        if not is_done:
            if expected is not None:
                ahead = pct >= expected
                ui.label(
                    "No ritmo ou adiantado" if ahead else "Atras do ritmo para o prazo"
                ).style(
                    f"font-size:15px;color:{theme.var('green') if ahead else theme.var('amber')};"
                    f"margin-top:2px"
                )
            if required:
                ui.label(f"Para o prazo: aportar {format_brl(required)}/mes").style(
                    f"font-size:15px;color:{theme.var('text2')};margin-top:2px"
                )
            if months_left is not None and months_left > 0:
                ui.label(f"No seu ritmo real: {months_left} mes(es) para concluir").style(
                    f"font-size:13px;color:{theme.var('textm')};margin-top:2px"
                )
            elif months_left is None:
                ui.label("Sem aportes suficientes para estimar o ritmo").style(
                    f"font-size:13px;color:{theme.var('textm')};margin-top:2px"
                )

        contributions = _contributions_dialog(goal, lambda: ui.navigate.reload())
        ui.button("Aportes", icon="savings", on_click=contributions.open).props(
            "flat dense no-caps"
        ).style(f"color:{theme.var('accent2')};font-size:14px;margin-top:8px;align-self:flex-start")

        ui.plotly(goal_progress_figure(goal, height=170)).style("width:100%;height:170px")


@ui.refreshable
def _goal_list(status_filter: str) -> None:
    with get_session() as session:
        status = None if status_filter == "all" else GoalStatus(status_filter)
        goal_list = goals_service.list_goals(session, status=status)

        if not goal_list:
            with components.card(padding="2rem"):
                components.empty_state("Nenhuma meta neste filtro", icon="flag")
            return

        with components.panel_grid(min_width="320px"):
            for goal in goal_list:
                _goal_card(session, goal)


def render() -> None:
    with page_frame("/metas"):
        with get_session() as session:
            all_goals = goals_service.list_goals(session)
            active = sum(1 for g in all_goals if g.status == GoalStatus.active)
            done = sum(1 for g in all_goals if g.status == GoalStatus.completed)
            total_target = sum(
                g.target_amount_cents for g in all_goals if g.status != GoalStatus.completed
            )
            total_saved = sum(
                g.current_amount_cents for g in all_goals if g.status != GoalStatus.completed
            )
            monthly_need = sum(
                goals_service.required_monthly_cents(g) or 0
                for g in all_goals
                if g.status == GoalStatus.active
            )

        with ui.row().style(
            "width:100%;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px"
        ):
            components.section_label(
                "Metas financeiras",
                help_text=(
                    "O progresso mostra o que voce ja guardou. Definir um prazo ativa o calculo "
                    "de aporte mensal necessario, usado no Disponivel para gastar do Dashboard."
                ),
            )
            with ui.row().style("gap:8px;align-items:center"):
                status_options = {"all": "Todas", **STATUS_LABELS}
                ui.select(
                    status_options,
                    value=GoalStatus.active.value,
                    on_change=lambda e: _goal_list.refresh(e.value),
                ).props("outlined dense").style("width:150px")
                dialog = _goal_form_dialog(lambda: ui.navigate.reload())
                ui.button("Nova meta", icon="add", on_click=dialog.open).props(
                    "no-caps unelevated"
                ).style(f"background:{theme.var('accent')};color:{theme.var('s1')}")

        if all_goals:
            with components.kpi_grid():
                components.kpi_card(
                    "Metas em andamento",
                    str(active),
                    sub=f"{done} concluida(s)",
                )
                components.kpi_card(
                    "Total guardado",
                    format_brl(total_saved),
                    sub=f"de {format_brl(total_target)} em metas abertas",
                )
                components.kpi_card(
                    "Aporte mensal necessario",
                    format_brl(monthly_need),
                    help_text=(
                        "Soma do que voce precisa guardar por mes para cumprir todas as metas "
                        "com prazo. Este valor ja e descontado do Disponivel para gastar."
                    ),
                )

        _goal_list(GoalStatus.active.value)

from __future__ import annotations

from nicegui import ui

from app import state, theme
from app.db import DB_PATH, get_session
from app.models import Category, Transaction
from app.services import accounts as accounts_service
from app.services import categories as categories_service
from app.services import goals as goals_service
from app.services import networth as networth_service
from app.services.money import format_brl
from app.ui import components
from app.ui.layout import page_frame
from sqlmodel import select


def _stat(label: str, value: str) -> None:
    with ui.column().style("gap:2px"):
        ui.label(label).style(
            f"font-size:{theme.font('meta')};color:{theme.var('textm')}"
        )
        ui.label(value).classes("money").style(
            f"font-size:{theme.font('title')};font-weight:600;color:{theme.var('text')}"
        )


def render() -> None:
    with page_frame("/perfil"):
        with get_session() as session:
            account_list = accounts_service.list_accounts(session)
            archived = accounts_service.list_accounts(session, include_archived=True)
            archived = [a for a in archived if a.archived]
            category_list = categories_service.list_categories(session)
            goal_list = goals_service.list_goals(session)
            tx_count = len(session.exec(select(Transaction)).all())
            sheet = networth_service.balance_sheet(session)

        components.section_label("Perfil e configuracoes")

        with components.panel_grid(min_width="380px"):
            with components.card(padding="1.25rem"):
                with ui.row().style("align-items:center;gap:14px;margin-bottom:14px"):
                    ui.icon("account_circle").style(
                        f"font-size:44px;color:{theme.var('accent')}"
                    )
                    with ui.column().style("gap:2px"):
                        ui.label("Uso pessoal").style(
                            f"font-size:{theme.font('title')};font-weight:600;"
                            f"color:{theme.var('text')}"
                        )
                        ui.label("Aplicativo local, sem conta e sem nuvem").style(
                            f"font-size:{theme.font('meta')};color:{theme.var('textm')}"
                        )

                with components.kpi_grid(min_width="150px"):
                    _stat("Contas ativas", str(len(account_list)))
                    _stat("Lancamentos", str(tx_count))
                    _stat("Categorias", str(len(category_list)))
                    _stat("Metas", str(len(goal_list)))

            with components.card(padding="1.25rem"):
                components.section_label(
                    "Ciclo financeiro",
                    help_text=(
                        "Se voce recebe salario no dia 25, definir 25 aqui faz o app tratar "
                        "de 25 a 24 como um mes, em vez de dia 1 a 31."
                    ),
                )
                day_input = ui.number(
                    "Dia de inicio do ciclo",
                    value=state.cycle_start_day(),
                    min=1,
                    max=31,
                    format="%.0f",
                ).props("outlined dense").style("width:100%;max-width:280px")

                def _save_cycle() -> None:
                    state.set_cycle_start_day(int(day_input.value or 1))
                    ui.notify("Ciclo financeiro atualizado")
                    ui.navigate.reload()

                ui.button("Salvar ciclo", on_click=_save_cycle).props(
                    "no-caps unelevated dense"
                ).style(
                    f"background:{theme.var('accent')};color:{theme.var('s1')};margin-top:10px"
                )

        with components.panel_grid(min_width="380px"):
            with components.card(padding="1.25rem"):
                components.section_label("Aparencia")
                ui.label(
                    "Linen e claro e aconchegante; Dusk e escuro, com destaques neon para "
                    "valores positivos e negativos."
                ).style(
                    f"font-size:{theme.font('meta')};color:{theme.var('textm')};"
                    f"margin-bottom:10px"
                )
                with ui.row().style("gap:8px"):
                    ui.button(
                        "Tema claro (Linen)" if theme.is_dark() else "Tema escuro (Dusk)",
                        icon=theme.current()["icon"],
                        on_click=lambda: theme.toggle(),
                    ).props("flat no-caps dense").style(
                        f"color:{theme.var('accent2')};"
                        f"border:1px solid {theme.var('border')}"
                    )

                ui.label("Tamanho da janela").style(
                    f"font-size:{theme.font('small')};color:{theme.var('text')};margin-top:16px"
                )
                with ui.row().style("gap:8px;margin-top:6px"):
                    for label, width, height in components.WINDOW_PRESETS:

                        def _apply(width=width, height=height) -> None:
                            state.set_window_size(width, height)
                            from nicegui import app as nicegui_app

                            if nicegui_app.native.main_window:
                                nicegui_app.native.main_window.resize(width, height)
                            ui.notify(f"Janela ajustada para {width}x{height}")

                        ui.button(f"{label} ({width}x{height})", on_click=_apply).props(
                            "flat no-caps dense"
                        ).style(
                            f"color:{theme.var('text2')};"
                            f"border:1px solid {theme.var('border')}"
                        )

            with components.card(padding="1.25rem"):
                components.section_label("Seus dados")
                ui.label(
                    "Tudo fica neste computador, num unico arquivo SQLite. Para fazer "
                    "backup, basta copiar o arquivo abaixo."
                ).style(
                    f"font-size:{theme.font('meta')};color:{theme.var('textm')};"
                    f"margin-bottom:8px"
                )
                ui.label(str(DB_PATH)).style(
                    f"font-size:{theme.font('meta')};color:{theme.var('text2')};"
                    f"font-family:monospace;word-break:break-all;"
                    f"background:{theme.var('s2')};padding:8px 10px;border-radius:6px"
                )
                def _backup() -> None:
                    from app.services import settings as settings_service

                    try:
                        path = settings_service.backup_database()
                    except Exception as exc:
                        ui.notify(f"Falha no backup: {exc}", color="negative")
                        return
                    ui.notify(f"Backup salvo em {path}", multi_line=True)

                ui.button("Fazer backup agora", icon="backup", on_click=_backup).props(
                    "no-caps unelevated dense"
                ).style(
                    f"background:{theme.var('accent')};color:{theme.var('s1')};margin-top:12px"
                ).tooltip(
                    "Cria uma copia datada do banco numa subpasta 'backups', ao lado do arquivo original"
                )

                with ui.row().style("gap:14px;margin-top:14px;flex-wrap:wrap"):
                    _stat("Ativos", format_brl(sheet["assets_cents"]))
                    _stat("Dividas", format_brl(sheet["liabilities_cents"]))
                    if archived:
                        _stat("Contas arquivadas", str(len(archived)))

        if archived:
            with components.card(padding="1.25rem"):
                components.section_label(
                    "Contas arquivadas",
                    help_text="Contas escondidas das telas, mas com historico preservado.",
                )
                for account in archived:
                    with ui.row().style(
                        f"width:100%;align-items:center;gap:12px;padding:10px 0;"
                        f"border-bottom:1px solid {theme.var('border')}"
                    ):
                        ui.icon("inventory_2").style(
                            f"color:{theme.var('textm')};font-size:20px"
                        )
                        ui.label(account.name).style(
                            f"font-size:{theme.font('body')};color:{theme.var('text')};flex:1"
                        )

                        def _restore(account_id=account.id) -> None:
                            with get_session() as session2:
                                accounts_service.set_archived(session2, account_id, False)
                            ui.navigate.reload()

                        ui.button("Restaurar", on_click=_restore).props(
                            "flat dense no-caps"
                        ).style(f"color:{theme.var('accent2')}")

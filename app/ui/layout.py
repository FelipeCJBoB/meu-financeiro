from __future__ import annotations

from contextlib import contextmanager

from nicegui import ui

from app import theme
from app.ui import components

NAV_ITEMS = [
    ("/", "dashboard", "Dashboard"),
    ("/lancamentos", "list_alt", "Lançamentos"),
    ("/orcamento", "pie_chart", "Orçamento"),
    ("/metas", "flag", "Metas"),
    ("/patrimonio", "trending_up", "Patrimônio"),
]


@contextmanager
def page_frame(active_path: str):
    theme.inject_head()

    with ui.column().style(
        f"width:100%;align-items:center;min-height:100vh;background:{theme.var('bg')};"
        f"padding:0;margin:0;gap:0"
    ):
        with ui.row().style(
            f"width:100%;max-width:1100px;align-items:center;justify-content:space-between;"
            f"padding:14px 24px;border-bottom:0.5px solid {theme.var('border')};"
            f"box-sizing:border-box;flex-wrap:wrap;gap:8px"
        ):
            with ui.row().style("align-items:center;gap:8px"):
                ui.icon("account_balance_wallet").style(
                    f"color:{theme.var('accent')};font-size:20px"
                )
                ui.label("Meu financeiro").style(
                    f"color:{theme.var('text')};font-weight:500;font-size:16px"
                )

            with ui.row().style("align-items:center;gap:4px;flex-wrap:wrap"):
                for path, icon, label in NAV_ITEMS:
                    is_active = path == active_path
                    btn = ui.button(
                        label, icon=icon, on_click=lambda p=path: ui.navigate.to(p)
                    ).props("flat no-caps dense")
                    bg = theme.var("s1") if is_active else "transparent"
                    fg = theme.var("text") if is_active else theme.var("text2")
                    btn.style(
                        f"color:{fg};background:{bg};border-radius:8px;font-size:13px;"
                        f"font-weight:{'500' if is_active else '400'}"
                    )

            with ui.row().style("align-items:center;gap:10px"):
                settings = components.settings_dialog()
                gear_el = ui.icon("settings").style(
                    f"cursor:pointer;color:{theme.var('text2')};font-size:20px"
                )
                gear_el.on("click", settings.open)

                icon_el = ui.icon(theme.current()["icon"]).style(
                    f"cursor:pointer;color:{theme.var('text2')};font-size:20px"
                )
                icon_el.on("click", lambda: theme.toggle(icon_el))

        with ui.column().style(
            "width:100%;align-items:center;padding:20px 24px;box-sizing:border-box"
        ):
            with ui.column().style("width:100%;max-width:1100px;gap:16px") as content:
                yield content

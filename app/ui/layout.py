from __future__ import annotations

from contextlib import contextmanager

from nicegui import ui

from app import theme

NAV_ITEMS = [
    ("/", "dashboard", "Dashboard"),
    ("/lancamentos", "list_alt", "Lançamentos"),
    ("/orcamento", "pie_chart", "Orçamento"),
    ("/metas", "flag", "Metas"),
    ("/patrimonio", "trending_up", "Patrimônio"),
    ("/perfil", "person", "Perfil"),
]

RAIL_WIDTH = 216


def _sidebar_css() -> None:
    """A fixed sidebar, always showing icon plus label.

    It used to sit collapsed at 64px and widen on hover, but the expansion floated
    over the page and covered whatever was underneath. Pushing the content sideways
    on hover would be worse: an accidental pass of the mouse would reflow the page
    and force every chart to redraw. At 216px on a 2560px screen the sidebar costs
    8% of the width and buys permanently readable labels - icon-only navigation
    makes the user guess what each symbol means.
    """
    ui.add_head_html(f"""
    <style>
      .rail {{
        position: fixed; top: 0; left: 0; bottom: 0;
        width: {RAIL_WIDTH}px;
        background: var(--app-s1);
        border-right: 1px solid var(--app-border);
        display: flex; flex-direction: column;
        padding: 14px 0; gap: 4px;
        overflow: hidden; white-space: nowrap;
        z-index: 1000;
      }}
      .rail-item {{
        display: flex; align-items: center; gap: 14px;
        height: 46px; min-height: 46px;
        padding: 0 20px;
        color: var(--app-text2); cursor: pointer;
        border-left: 3px solid transparent;
        transition: background 140ms ease-out, color 140ms ease-out;
      }}
      .rail-item:hover {{ background: var(--app-s2); color: var(--app-text); }}
      .rail-item.active {{
        color: var(--app-text);
        background: var(--app-s2);
        border-left-color: var(--app-accent);
      }}
      .rail-item .label {{ font-size: {theme.font("body")}; }}
      .rail-spacer {{ flex: 1; }}
      .page-body {{ margin-left: {RAIL_WIDTH}px; }}
    </style>
    """)


@contextmanager
def page_frame(active_path: str):
    theme.inject_head()
    _sidebar_css()

    with ui.element("div").classes("rail"):
        with ui.element("div").classes("rail-item").style("cursor:default"):
            ui.icon("account_balance_wallet").style(
                f"color:{theme.var('accent')};font-size:24px;min-width:24px"
            )
            ui.label("Meu financeiro").classes("label").style(
                f"color:{theme.var('text')};font-weight:600"
            )

        ui.element("div").style(
            f"height:1px;background:{theme.var('border')};margin:10px 12px"
        )

        for path, icon, label in NAV_ITEMS:
            classes = "rail-item active" if path == active_path else "rail-item"
            item = ui.element("div").classes(classes)
            with item:
                ui.icon(icon).style("font-size:22px;min-width:24px")
                ui.label(label).classes("label")
            item.on("click", lambda p=path: ui.navigate.to(p))

        ui.element("div").classes("rail-spacer")

        theme_item = ui.element("div").classes("rail-item")
        with theme_item:
            ui.icon(theme.current()["icon"]).style("font-size:22px;min-width:24px")
            ui.label("Tema claro" if theme.is_dark() else "Tema escuro").classes("label")
        theme_item.on("click", lambda: theme.toggle())

    # The offset has to be inline: the blanket `margin:0` that used to sit here beat
    # the stylesheet rule, so the page sat underneath the sidebar all along and the
    # hover expansion merely made the overlap obvious.
    with ui.column().classes("page-body").style(
        f"width:calc(100% - {RAIL_WIDTH}px);align-items:center;min-height:100vh;"
        f"background:{theme.var('bg')};padding:0;margin:0 0 0 {RAIL_WIDTH}px;gap:0"
    ):
        with ui.column().style(
            "width:100%;align-items:center;padding:22px 28px;box-sizing:border-box"
        ):
            # 2400px lets a 2560px-wide (2K) monitor actually fill the viewport
            # instead of leaving a wide empty gutter on each side.
            with ui.column().style("width:100%;max-width:2400px;gap:18px") as content:
                yield content

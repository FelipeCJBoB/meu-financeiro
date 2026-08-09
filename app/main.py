from __future__ import annotations

import os

from nicegui import native, ui

from app.db import init_db
from app.ui import dashboard, lancamentos, metas, orcamento, patrimonio


@ui.page("/")
def index_page() -> None:
    dashboard.render()


@ui.page("/lancamentos")
def lancamentos_page() -> None:
    lancamentos.render()


@ui.page("/orcamento")
def orcamento_page() -> None:
    orcamento.render()


@ui.page("/metas")
def metas_page() -> None:
    metas.render()


@ui.page("/patrimonio")
def patrimonio_page() -> None:
    patrimonio.render()


def main() -> None:
    init_db()
    native_mode = os.getenv("MEUFINANCEIRO_NATIVE", "1") != "0"
    port = (
        native.find_open_port()
        if native_mode
        else int(os.getenv("MEUFINANCEIRO_PORT", "8420"))
    )
    ui.run(
        title="Meu financeiro",
        native=native_mode,
        window_size=(1500, 940) if native_mode else None,
        reload=False,
        show=False,
        port=port,
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()

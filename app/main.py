from __future__ import annotations

import os

from nicegui import native, ui

from app import state
from app.db import init_db
from app.ui import dashboard, lancamentos, metas, orcamento, patrimonio, perfil


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


@ui.page("/perfil")
def perfil_page() -> None:
    perfil.render()


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
        window_size=state.window_size() if native_mode else None,
        reload=False,
        show=False,
        port=port,
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()

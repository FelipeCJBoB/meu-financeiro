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


def _auto_snapshot() -> None:
    """One automatic net-worth record per month, on first launch of that month."""
    from app.db import get_session
    from app.services import networth

    try:
        with get_session() as session:
            networth.ensure_monthly_snapshot(session)
    except Exception:
        pass  # never block startup over a bookkeeping convenience


def main() -> None:
    init_db()
    _auto_snapshot()
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

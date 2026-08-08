from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import Category, CategoryKind


def _data_dir() -> Path:
    base = os.getenv("APPDATA") or str(Path.home())
    path = Path(base) / "MeuFinanceiro"
    path.mkdir(parents=True, exist_ok=True)
    return path


_override = os.getenv("MEUFINANCEIRO_DB_PATH")
DB_PATH = Path(_override) if _override else _data_dir() / "dados.db"
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


DEFAULT_CATEGORIES: list[tuple[str, str, str, CategoryKind]] = [
    ("Moradia", "home", "#5b8dc7", CategoryKind.expense),
    ("Mercado", "shopping_cart", "#d98764", CategoryKind.expense),
    ("Transporte", "directions_car", "#4faf97", CategoryKind.expense),
    ("Lazer", "movie", "#c99a3e", CategoryKind.expense),
    ("Saude", "favorite", "#d47ba0", CategoryKind.expense),
    ("Educacao", "school", "#7ea854", CategoryKind.expense),
    ("Salario", "account_balance", "#4faf97", CategoryKind.income),
    ("Outras receitas", "paid", "#5b8dc7", CategoryKind.income),
]


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _seed_categories(session)


def _seed_categories(session: Session) -> None:
    existing = session.exec(select(Category)).first()
    if existing is not None:
        return
    for name, icon, color, kind in DEFAULT_CATEGORIES:
        session.add(Category(name=name, icon=icon, color=color, kind=kind))
    session.commit()


def get_session() -> Session:
    return Session(engine)

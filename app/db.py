from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from sqlalchemy import event, text
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


# Slot in the themed categorical ramp, not a hex: see design.CATEGORICAL. The
# hex kept alongside is only a fallback for code paths that read `color` raw.
# The old seed handed #4faf97 to both Transporte and Salario, and #5b8dc7 to
# both Moradia and Outras receitas, so colour stopped identifying a category -
# distinct slots are what fixes that.
DEFAULT_CATEGORIES: list[tuple[str, str, int, CategoryKind]] = [
    ("Moradia", "home", 0, CategoryKind.expense),
    ("Mercado", "shopping_cart", 1, CategoryKind.expense),
    ("Transporte", "directions_car", 2, CategoryKind.expense),
    ("Lazer", "movie", 3, CategoryKind.expense),
    ("Saude", "favorite", 5, CategoryKind.expense),
    ("Educacao", "school", 4, CategoryKind.expense),
    ("Salario", "account_balance", 6, CategoryKind.income),
    ("Outras receitas", "paid", 7, CategoryKind.income),
]

# What the seed used to write. A category still carrying one of these was never
# recoloured by hand, so the backfill may safely adopt it into a slot; anything
# else is a deliberate choice and is left untouched.
LEGACY_SEED_COLORS = {
    "Moradia": "#5b8dc7",
    "Mercado": "#d98764",
    "Transporte": "#4faf97",
    "Lazer": "#c99a3e",
    "Saude": "#d47ba0",
    "Educacao": "#7ea854",
    "Salario": "#4faf97",
    "Outras receitas": "#5b8dc7",
}


MIGRATIONS: list[tuple[str, str, str]] = [
    ("goals", "created_at", f"TEXT DEFAULT '{date.today().isoformat()}'"),
    ("settings", "window_width", "INTEGER DEFAULT 2560"),
    ("settings", "window_height", "INTEGER DEFAULT 1440"),
    ("goals", "status", "TEXT DEFAULT 'active'"),
    ("settings", "theme_name", "TEXT DEFAULT 'linen'"),
    ("transactions", "balance_after_cents", "INTEGER"),
    ("transactions", "already_settled", "INTEGER DEFAULT 0"),
    ("categories", "color_slot", "INTEGER"),
]


def _run_migrations() -> None:
    with engine.connect() as conn:
        for table, column, ddl in MIGRATIONS:
            existing = {
                row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))
            }
            if column not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
        conn.commit()


def _backfill_goal_contributions(session: Session) -> None:
    """Goals created before the contribution log existed carry a balance with no
    history. Seed one opening entry so the log always sums to the stored total."""
    from app.models import Goal, GoalContribution

    goals = session.exec(select(Goal).where(Goal.current_amount_cents > 0)).all()
    for goal in goals:
        has_history = session.exec(
            select(GoalContribution).where(GoalContribution.goal_id == goal.id)
        ).first()
        if has_history is not None:
            continue
        session.add(
            GoalContribution(
                goal_id=goal.id,
                date=goal.created_at,
                amount_cents=goal.current_amount_cents,
                note="Saldo inicial",
            )
        )
    session.commit()


def _backfill_adjustment_anchors(session: Session) -> None:
    """Balance sync entries made before balance_after_cents existed only stored
    a delta, which the current-balance calc can no longer use safely once other
    transactions get added out of order around them - see account_balance_cents.
    Reconstruct the absolute value each one resolved to by replaying every
    transaction on that account in creation order (id), exactly like the old
    balance calc summed them, and snapshotting the running total the moment
    each adjustment fired. This runs once per adjustment, ever - after today,
    every new "Ajustar saldo" already stores its own anchor at creation time."""
    from app.models import Account, Transaction, TransactionType

    accounts = session.exec(select(Account)).all()
    for account in accounts:
        pending = session.exec(
            select(Transaction).where(
                Transaction.account_id == account.id,
                Transaction.type == TransactionType.adjustment,
                Transaction.balance_after_cents.is_(None),
            )
        ).first()
        if pending is None:
            continue

        own = session.exec(
            select(Transaction)
            .where(Transaction.account_id == account.id)
            .order_by(Transaction.id)
        ).all()
        incoming = session.exec(
            select(Transaction)
            .where(
                Transaction.transfer_account_id == account.id,
                Transaction.type == TransactionType.transfer,
            )
            .order_by(Transaction.id)
        ).all()
        events = sorted(
            [(tx.id, False, tx) for tx in own] + [(tx.id, True, tx) for tx in incoming],
            key=lambda e: e[0],
        )

        running = account.initial_balance_cents
        for _id, is_incoming_transfer, tx in events:
            if is_incoming_transfer:
                running += tx.amount_cents
                continue
            if tx.type == TransactionType.income:
                running += tx.amount_cents
            elif tx.type in (TransactionType.expense, TransactionType.transfer):
                running -= tx.amount_cents
            elif tx.type == TransactionType.adjustment:
                running += tx.amount_cents
                if tx.balance_after_cents is None:
                    tx.balance_after_cents = running
                    session.add(tx)
        session.commit()


def _backfill_category_slots(session: Session) -> None:
    """Adopt the untouched default categories into the themed ramp.

    Only categories that still carry the exact colour the old seed wrote are
    migrated: that is the evidence the user never picked a colour there. A
    category with any other colour keeps a NULL slot and goes on rendering its
    own hex, so nobody's choice is overwritten. Idempotent - a category that
    already has a slot is skipped."""
    from app.db import DEFAULT_CATEGORIES as defaults

    slots = {name: slot for name, _icon, slot, _kind in defaults}
    categories = session.exec(select(Category).where(Category.color_slot.is_(None))).all()
    changed = False
    for category in categories:
        legacy = LEGACY_SEED_COLORS.get(category.name)
        if legacy is None or category.color.lower() != legacy.lower():
            continue
        category.color_slot = slots[category.name]
        session.add(category)
        changed = True
    if changed:
        session.commit()


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    _run_migrations()
    with Session(engine) as session:
        _seed_categories(session)
        _backfill_goal_contributions(session)
        _backfill_adjustment_anchors(session)
        _backfill_category_slots(session)


def _seed_categories(session: Session) -> None:
    from app import design

    existing = session.exec(select(Category)).first()
    if existing is not None:
        return
    for name, icon, slot, kind in DEFAULT_CATEGORIES:
        session.add(
            Category(
                name=name,
                icon=icon,
                color=design.CATEGORICAL["linen"][slot],
                color_slot=slot,
                kind=kind,
            )
        )
    session.commit()


def get_session() -> Session:
    return Session(engine)

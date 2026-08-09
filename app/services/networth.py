from __future__ import annotations

import json
from datetime import date

from sqlmodel import Session, select

from app.models import NetWorthSnapshot, Transaction, TransactionType
from app.services.accounts import account_balance_cents, list_accounts


def current_net_worth(session: Session) -> tuple[int, dict[int, int]]:
    breakdown: dict[int, int] = {}
    total = 0
    for account in list_accounts(session):
        balance = account_balance_cents(session, account.id)
        breakdown[account.id] = balance
        total += balance
    return total, breakdown


def create_snapshot(session: Session, *, on_date: date | None = None) -> NetWorthSnapshot:
    on_date = on_date or date.today()
    total, breakdown = current_net_worth(session)
    snapshot = NetWorthSnapshot(
        date=on_date,
        net_worth_cents=total,
        breakdown_json=json.dumps(breakdown),
    )
    session.add(snapshot)
    session.commit()
    session.refresh(snapshot)
    return snapshot


def trend(session: Session, *, months: int = 6) -> list[tuple[str, int]]:
    snapshots = session.exec(select(NetWorthSnapshot).order_by(NetWorthSnapshot.date)).all()
    by_month: dict[str, int] = {}
    for snap in snapshots:
        by_month[snap.date.strftime("%Y-%m")] = snap.net_worth_cents
    items = sorted(by_month.items())
    return items[-months:]


def _cumulative_breakdown(session: Session, as_of: date) -> tuple[int, int]:
    """Splits net worth as-of a date into contributed cash vs. gains.

    Contributed = starting balances + income - expenses (real money moved in).
    Gains = sum of manual balance adjustments (how account_balance_cents already
    treats investment revaluation), i.e. value change not explained by cash flow.
    """
    accounts = list_accounts(session, include_archived=True)
    contributed = sum(account.initial_balance_cents for account in accounts)

    incomes = session.exec(
        select(Transaction).where(
            Transaction.type == TransactionType.income, Transaction.date <= as_of
        )
    ).all()
    expenses = session.exec(
        select(Transaction).where(
            Transaction.type == TransactionType.expense, Transaction.date <= as_of
        )
    ).all()
    adjustments = session.exec(
        select(Transaction).where(
            Transaction.type == TransactionType.adjustment, Transaction.date <= as_of
        )
    ).all()

    contributed += sum(tx.amount_cents for tx in incomes) - sum(tx.amount_cents for tx in expenses)
    gains = sum(tx.amount_cents for tx in adjustments)
    return contributed, gains


def evolution_breakdown(session: Session, *, months: int = 6) -> list[dict]:
    snapshots = session.exec(select(NetWorthSnapshot).order_by(NetWorthSnapshot.date)).all()
    by_month: dict[str, date] = {}
    for snap in snapshots:
        by_month[snap.date.strftime("%Y-%m")] = snap.date
    items = sorted(by_month.items())[-months:]

    rows = []
    for month_label, as_of in items:
        contributed_cents, gain_cents = _cumulative_breakdown(session, as_of)
        rows.append(
            {"month": month_label, "contributed_cents": contributed_cents, "gain_cents": gain_cents}
        )
    return rows


def composition(session: Session) -> list[dict]:
    _total, breakdown = current_net_worth(session)
    rows = []
    for account in list_accounts(session):
        rows.append(
            {
                "account": account,
                "balance_cents": breakdown.get(account.id, 0),
            }
        )
    rows.sort(key=lambda row: row["balance_cents"], reverse=True)
    return rows

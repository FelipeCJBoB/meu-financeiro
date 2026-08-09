from __future__ import annotations

import json
from datetime import date

from sqlmodel import Session, select

from app.models import (
    LIABILITY_TYPES,
    LIQUID_TYPES,
    NetWorthSnapshot,
    Transaction,
    TransactionType,
)
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


def balance_sheet(session: Session) -> dict:
    """Splits accounts into assets and liabilities instead of one mixed signed total.

    A credit card at -R$300 is a debt, not a 'negative asset' - keeping them in one
    column hides how much you own and how much you owe.
    """
    assets: list[dict] = []
    liabilities: list[dict] = []
    liquid_cents = 0
    illiquid_cents = 0

    for account in list_accounts(session):
        balance = account_balance_cents(session, account.id)
        row = {"account": account, "balance_cents": balance}
        if account.type in LIABILITY_TYPES or balance < 0:
            liabilities.append({**row, "balance_cents": abs(balance)})
        else:
            assets.append(row)
            if account.type in LIQUID_TYPES:
                liquid_cents += balance
            else:
                illiquid_cents += balance

    assets.sort(key=lambda row: row["balance_cents"], reverse=True)
    liabilities.sort(key=lambda row: row["balance_cents"], reverse=True)

    assets_cents = sum(row["balance_cents"] for row in assets)
    liabilities_cents = sum(row["balance_cents"] for row in liabilities)

    return {
        "assets": assets,
        "liabilities": liabilities,
        "assets_cents": assets_cents,
        "liabilities_cents": liabilities_cents,
        "net_worth_cents": assets_cents - liabilities_cents,
        "liquid_cents": liquid_cents,
        "illiquid_cents": illiquid_cents,
    }


def health_indicators(session: Session) -> dict:
    """Debt ratio and savings rate - two numbers that say more than the total alone."""
    sheet = balance_sheet(session)
    debt_ratio = (
        sheet["liabilities_cents"] / sheet["assets_cents"] if sheet["assets_cents"] > 0 else None
    )

    incomes = session.exec(
        select(Transaction).where(Transaction.type == TransactionType.income)
    ).all()
    expenses = session.exec(
        select(Transaction).where(Transaction.type == TransactionType.expense)
    ).all()
    income_total = sum(tx.amount_cents for tx in incomes)
    expense_total = sum(tx.amount_cents for tx in expenses)
    savings_rate = (income_total - expense_total) / income_total if income_total > 0 else None

    return {
        "debt_ratio": debt_ratio,
        "savings_rate": savings_rate,
        "liquid_cents": sheet["liquid_cents"],
        "illiquid_cents": sheet["illiquid_cents"],
    }


def committed_to_goals_cents(session: Session) -> int:
    from app.models import GoalStatus
    from app.services.goals import list_goals

    return sum(
        goal.current_amount_cents
        for goal in list_goals(session)
        if goal.status != GoalStatus.completed
    )


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

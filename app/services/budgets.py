from __future__ import annotations

from datetime import date

from sqlmodel import Session, select

from app.models import Budget, Category, CategoryKind, Transaction, TransactionSplit, TransactionType
from app.services.money import month_bounds, month_key_for_date


def set_budget(session: Session, *, category_id: int, month: str, amount_cents: int) -> Budget:
    existing = session.exec(
        select(Budget).where(Budget.category_id == category_id, Budget.month == month)
    ).first()
    if existing:
        existing.amount_cents = amount_cents
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    budget = Budget(category_id=category_id, month=month, amount_cents=amount_cents)
    session.add(budget)
    session.commit()
    session.refresh(budget)
    return budget


def get_budget(session: Session, category_id: int, month: str) -> Budget | None:
    return session.exec(
        select(Budget).where(Budget.category_id == category_id, Budget.month == month)
    ).first()


def spent_in_category(
    session: Session, category_id: int, month: str, cycle_start_day: int = 1
) -> int:
    start, end = month_bounds(month, cycle_start_day)

    direct = session.exec(
        select(Transaction).where(
            Transaction.category_id == category_id,
            Transaction.type == TransactionType.expense,
            Transaction.date >= start,
            Transaction.date <= end,
        )
    ).all()
    total = sum(tx.amount_cents for tx in direct)

    split_rows = session.exec(
        select(TransactionSplit, Transaction)
        .join(Transaction, TransactionSplit.transaction_id == Transaction.id)
        .where(
            TransactionSplit.category_id == category_id,
            Transaction.date >= start,
            Transaction.date <= end,
        )
    ).all()
    total += sum(split.amount_cents for split, _tx in split_rows)

    return total


def budget_progress(session: Session, month: str, cycle_start_day: int = 1) -> list[dict]:
    budgets = session.exec(select(Budget).where(Budget.month == month)).all()
    result = []
    for budget in budgets:
        category = session.get(Category, budget.category_id)
        if category is None or category.kind == CategoryKind.income:
            continue
        spent = spent_in_category(session, budget.category_id, month, cycle_start_day)
        result.append(
            {
                "category": category,
                "budget_cents": budget.amount_cents,
                "spent_cents": spent,
                "pct": (spent / budget.amount_cents) if budget.amount_cents else 0.0,
            }
        )
    result.sort(key=lambda row: row["pct"], reverse=True)
    return result


def month_summary(session: Session, month: str, cycle_start_day: int = 1) -> dict:
    rows = budget_progress(session, month, cycle_start_day)
    return {
        "budget_cents": sum(row["budget_cents"] for row in rows),
        "spent_cents": sum(row["spent_cents"] for row in rows),
    }


def spend_pace(session: Session, month: str, cycle_start_day: int = 1) -> dict | None:
    """Linear run-rate projection: only meaningful for the cycle still in progress."""
    today = date.today()
    if month != month_key_for_date(today, cycle_start_day):
        return None

    start, end = month_bounds(month, cycle_start_day)
    days_in_month = (end - start).days + 1
    days_elapsed = min((today - start).days + 1, days_in_month)

    summary = month_summary(session, month, cycle_start_day)
    if summary["budget_cents"] == 0 or days_elapsed <= 0:
        return None

    projected_cents = round(summary["spent_cents"] / days_elapsed * days_in_month)
    return {
        "days_elapsed": days_elapsed,
        "days_in_month": days_in_month,
        "spent_cents": summary["spent_cents"],
        "projected_cents": projected_cents,
        "budget_cents": summary["budget_cents"],
        "over_by_cents": projected_cents - summary["budget_cents"],
    }

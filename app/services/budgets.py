from __future__ import annotations

from datetime import date

from sqlmodel import Session, select

from app.models import Budget, Category, CategoryKind, Transaction, TransactionSplit, TransactionType
from app.services.money import month_bounds, month_key_for_date, previous_month


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


def copy_from_previous_month(session: Session, month: str, *, overwrite: bool = False) -> int:
    """Carries last cycle's limits into this one. Returns how many were copied."""
    source = previous_month(month)
    source_budgets = session.exec(select(Budget).where(Budget.month == source)).all()
    copied = 0
    for budget in source_budgets:
        existing = get_budget(session, budget.category_id, month)
        if existing is not None and not overwrite:
            continue
        set_budget(
            session,
            category_id=budget.category_id,
            month=month,
            amount_cents=budget.amount_cents,
        )
        copied += 1
    return copied


def average_spent_cents(
    session: Session, category_id: int, *, months: int = 3, end_month: str, cycle_start_day: int = 1
) -> int:
    labels = [end_month]
    for _ in range(months - 1):
        labels.append(previous_month(labels[-1]))
    labels = labels[1:]  # exclude the in-progress cycle from the average
    if not labels:
        return 0
    total = sum(spent_in_category(session, category_id, m, cycle_start_day) for m in labels)
    return round(total / len(labels))


def unbudgeted_categories(session: Session, month: str, cycle_start_day: int = 1) -> list[dict]:
    """Expense categories with spending this cycle but no limit set - the silent leak."""
    rows = []
    categories = session.exec(
        select(Category).where(
            Category.archived == False,  # noqa: E712
            Category.kind != CategoryKind.income,
        )
    ).all()
    for category in categories:
        if get_budget(session, category.id, month) is not None:
            continue
        spent = spent_in_category(session, category.id, month, cycle_start_day)
        suggestion = average_spent_cents(
            session, category.id, months=4, end_month=month, cycle_start_day=cycle_start_day
        )
        if spent == 0 and suggestion == 0:
            continue
        rows.append(
            {"category": category, "spent_cents": spent, "suggested_cents": max(spent, suggestion)}
        )
    rows.sort(key=lambda row: row["spent_cents"], reverse=True)
    return rows


def category_pace(
    session: Session, category_id: int, month: str, cycle_start_day: int = 1
) -> dict | None:
    """Per-category run-rate, but only where a daily rate actually means something.

    Linear extrapolation assumes spending trickles in day by day. That holds for
    groceries; it is nonsense for rent, which is paid once and would be projected
    as if it repeated every day. So we only project when the category shows a
    spread-out pattern (2+ transactions) and is not already over budget.
    """
    today = date.today()
    if month != month_key_for_date(today, cycle_start_day):
        return None
    budget = get_budget(session, category_id, month)
    if budget is None or budget.amount_cents <= 0:
        return None

    spent = spent_in_category(session, category_id, month, cycle_start_day)
    if spent >= budget.amount_cents:
        return None

    if len(category_transactions(session, category_id, month, cycle_start_day)) < 2:
        return None

    start, end = month_bounds(month, cycle_start_day)
    days_in_month = (end - start).days + 1
    days_elapsed = min(max((today - start).days + 1, 1), days_in_month)
    projected = round(spent / days_elapsed * days_in_month)
    return {
        "spent_cents": spent,
        "budget_cents": budget.amount_cents,
        "projected_cents": projected,
        "over_by_cents": projected - budget.amount_cents,
        "days_elapsed": days_elapsed,
        "days_in_month": days_in_month,
    }


def budget_history(
    session: Session, *, end_month: str, months: int = 6, cycle_start_day: int = 1
) -> list[dict]:
    """Budgeted vs. actual per cycle - answers 'is my budget realistic?'."""
    labels = [end_month]
    for _ in range(months - 1):
        labels.append(previous_month(labels[-1]))
    labels.reverse()

    rows = []
    for label in labels:
        summary = month_summary(session, label, cycle_start_day)
        rows.append(
            {
                "month": label,
                "budget_cents": summary["budget_cents"],
                "spent_cents": summary["spent_cents"],
            }
        )
    return rows


def category_transactions(
    session: Session, category_id: int, month: str, cycle_start_day: int = 1
) -> list[Transaction]:
    """The transactions behind a category's number, for drill-down."""
    start, end = month_bounds(month, cycle_start_day)
    direct = session.exec(
        select(Transaction).where(
            Transaction.category_id == category_id,
            Transaction.type == TransactionType.expense,
            Transaction.date >= start,
            Transaction.date <= end,
        )
    ).all()
    split_rows = session.exec(
        select(Transaction)
        .join(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .where(
            TransactionSplit.category_id == category_id,
            Transaction.date >= start,
            Transaction.date <= end,
        )
    ).all()
    merged = {tx.id: tx for tx in list(direct) + list(split_rows)}
    return sorted(merged.values(), key=lambda tx: tx.date, reverse=True)


def spend_pace(session: Session, month: str, cycle_start_day: int = 1) -> dict | None:
    """Projection for the whole cycle, splitting fixed from variable spending.

    Extrapolating everything linearly overstates the total badly: a rent paid once
    on day 5 would be projected as if it repeated all month. Categories with a
    single transaction are treated as already-settled fixed costs and carried at
    face value; only categories with spread-out spending get extrapolated.
    """
    today = date.today()
    if month != month_key_for_date(today, cycle_start_day):
        return None

    start, end = month_bounds(month, cycle_start_day)
    days_in_month = (end - start).days + 1
    days_elapsed = min((today - start).days + 1, days_in_month)

    summary = month_summary(session, month, cycle_start_day)
    if summary["budget_cents"] == 0 or days_elapsed <= 0:
        return None

    fixed_cents = 0
    variable_cents = 0
    for row in budget_progress(session, month, cycle_start_day):
        category_id = row["category"].id
        tx_count = len(category_transactions(session, category_id, month, cycle_start_day))
        if tx_count < 2:
            fixed_cents += row["spent_cents"]
        else:
            variable_cents += row["spent_cents"]

    projected_variable = round(variable_cents / days_elapsed * days_in_month)
    projected_cents = fixed_cents + projected_variable

    return {
        "days_elapsed": days_elapsed,
        "days_in_month": days_in_month,
        "spent_cents": summary["spent_cents"],
        "fixed_cents": fixed_cents,
        "variable_cents": variable_cents,
        "projected_cents": projected_cents,
        "budget_cents": summary["budget_cents"],
        "over_by_cents": projected_cents - summary["budget_cents"],
    }

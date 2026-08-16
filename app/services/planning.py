from __future__ import annotations

from datetime import date

from sqlmodel import Session, select

from app.models import Account, Category, Goal, Transaction, TransactionSplit, TransactionType
from app.services.budgets import budget_progress
from app.services.goals import list_goals
from app.services.money import (
    month_bounds,
    month_key,
    month_key_for_date,
    months_between,
    previous_month,
)
from app.services.recurring import due_recurring_rules, list_recurring_rules
from app.services.transactions import month_totals


def goal_monthly_need_cents(goal: Goal, as_of_month: str) -> int:
    """Amount to set aside this month to reach a goal by its target date, if any."""
    if not goal.target_date or goal.archived:
        return 0
    remaining = max(0, goal.target_amount_cents - goal.current_amount_cents)
    if remaining == 0:
        return 0
    target_month = month_key(goal.target_date)
    months_left = max(1, months_between(as_of_month, target_month))
    return round(remaining / months_left)


def available_to_spend(session: Session, month: str, cycle_start_day: int = 1) -> dict | None:
    """Simplifi-style headline number: income minus bills, full stop.

    Goal pacing used to be subtracted here too, but a goal is a target the user
    set for themselves, not an obligation - folding it into "how much can I
    spend" made a flexible plan read as a debt, and made this number swing on
    something that isn't really about spending money. goals_need_cents is still
    computed and returned (the Metas card on the dashboard uses it), it just no
    longer touches available_cents.

    Only meaningful for the cycle currently in progress - a closed month has no
    "available to spend" left to decide on.
    """
    today = date.today()
    if month != month_key_for_date(today, cycle_start_day):
        return None

    start, end = month_bounds(month, cycle_start_day)
    totals = month_totals(session, month, cycle_start_day)

    upcoming_income_cents = 0
    upcoming_expense_cents = 0
    for rule in list_recurring_rules(session):
        if rule.next_due_date <= today or not (start <= rule.next_due_date <= end):
            continue
        if rule.type == TransactionType.income:
            upcoming_income_cents += rule.amount_cents
        elif rule.type == TransactionType.expense:
            upcoming_expense_cents += rule.amount_cents

    goals_need_cents = sum(goal_monthly_need_cents(g, month) for g in list_goals(session))

    income_total_cents = totals["income_cents"] + upcoming_income_cents
    bills_cents = totals["expense_cents"] + upcoming_expense_cents

    return {
        "income_total_cents": income_total_cents,
        "spent_cents": totals["expense_cents"],
        "upcoming_expense_cents": upcoming_expense_cents,
        "bills_cents": bills_cents,
        "goals_need_cents": goals_need_cents,
        "available_cents": income_total_cents - bills_cents,
    }


def daily_allowance(session: Session, month: str, cycle_start_day: int = 1) -> dict | None:
    """Simplifi-style 'what's left to spend, per day, for the rest of the cycle'."""
    available = available_to_spend(session, month, cycle_start_day)
    if available is None:
        return None
    today = date.today()
    _start, end = month_bounds(month, cycle_start_day)
    days_remaining = max(1, (end - today).days + 1)
    return {
        "available_cents": available["available_cents"],
        "days_remaining": days_remaining,
        "per_day_cents": round(available["available_cents"] / days_remaining),
    }


def overall_status(session: Session, month: str, cycle_start_day: int = 1) -> dict:
    """Traffic-light state driven by the worst signal, not an averaged score.

    A composite 0-100 score can hide a real problem behind a good average - a
    consumer financial-health index (Atlas) deliberately reports three separate
    scores instead of one for exactly this reason. We surface the worst signal.

    A goal running behind pace is never the worst signal on its own: it is a
    choice the user made for themselves, not a bill collector. Only bills
    outrunning income - a real, non-negotiable shortfall - escalates to critical.
    """
    overdue = due_recurring_rules(session)
    over_budget = [row for row in budget_progress(session, month, cycle_start_day) if row["pct"] > 1.0]
    available = available_to_spend(session, month, cycle_start_day)
    available_negative = available is not None and available["available_cents"] < 0
    goals_behind = (
        available is not None
        and not available_negative
        and available["goals_need_cents"] > available["available_cents"]
    )

    if overdue or available_negative:
        level = "critical"
    elif over_budget or goals_behind:
        level = "warning"
    else:
        level = "ok"

    return {
        "level": level,
        "overdue_rules": overdue,
        "over_budget_categories": over_budget,
        "available_negative": available_negative,
        "goals_behind": goals_behind,
    }


def emergency_fund_months(session: Session, month: str, cycle_start_day: int = 1) -> dict | None:
    """How many months of expenses your reachable money covers.

    Uses liquid assets only, not total net worth: an apartment or a locked-in
    investment does not pay next month's groceries, so counting it here would
    overstate the cushion badly.
    """
    from app.services.networth import balance_sheet
    from app.services.transactions import monthly_series

    sheet = balance_sheet(session)
    rows = monthly_series(
        session, end_month=previous_month(month), months=6, cycle_start_day=cycle_start_day
    )
    spending = [r["expense_cents"] for r in rows if r["expense_cents"] > 0]
    if not spending:
        return None
    average_expense = sum(spending) / len(spending)
    if average_expense <= 0:
        return None
    return {
        "months_covered": sheet["liquid_cents"] / average_expense,
        "liquid_cents": sheet["liquid_cents"],
        "average_expense_cents": round(average_expense),
    }


def savings_rate(
    session: Session, start: date, end: date, *, account_id: int | None = None
) -> float | None:
    """Share of income that did not get spent, for the selected period."""
    from app.services.transactions import range_totals

    totals = range_totals(session, start, end, account_id=account_id)
    if totals["income_cents"] <= 0:
        return None
    return (totals["income_cents"] - totals["expense_cents"]) / totals["income_cents"]


def worst_budget_category(session: Session, month: str, cycle_start_day: int = 1) -> dict | None:
    rows = budget_progress(session, month, cycle_start_day)
    if not rows:
        return None
    worst = rows[0]
    if worst["pct"] < 0.8:
        return None
    return worst


def sankey_data(
    session: Session,
    month: str,
    cycle_start_day: int = 1,
    *,
    start: date | None = None,
    end: date | None = None,
    account_id: int | None = None,
) -> dict | None:
    """Money-flow graph: income -> account -> expenses/transfers/leftover."""
    if start is None or end is None:
        start, end = month_bounds(month, cycle_start_day)
    stmt = select(Transaction).where(Transaction.date >= start, Transaction.date <= end)
    if account_id is not None:
        stmt = stmt.where(Transaction.account_id == account_id)
    txs = session.exec(stmt).all()
    if not txs:
        return None

    accounts = {a.id: a for a in session.exec(select(Account)).all()}
    categories = {c.id: c for c in session.exec(select(Category)).all()}

    labels: list[str] = []
    label_index: dict[str, int] = {}

    def idx(label: str) -> int:
        if label not in label_index:
            label_index[label] = len(labels)
            labels.append(label)
        return label_index[label]

    links: dict[tuple[int, int], int] = {}

    def add_link(source_label: str, target_label: str, amount: int) -> None:
        if amount <= 0:
            return
        key = (idx(source_label), idx(target_label))
        links[key] = links.get(key, 0) + amount

    account_in: dict[int, int] = {}
    account_out: dict[int, int] = {}

    for tx in txs:
        account = accounts.get(tx.account_id)
        account_label = account.name if account else "Conta"

        if tx.type == TransactionType.income:
            category = categories.get(tx.category_id)
            add_link(category.name if category else "Receita", account_label, tx.amount_cents)
            account_in[tx.account_id] = account_in.get(tx.account_id, 0) + tx.amount_cents

        elif tx.type == TransactionType.expense:
            splits = session.exec(
                select(TransactionSplit).where(TransactionSplit.transaction_id == tx.id)
            ).all()
            allocations = (
                [(s.category_id, s.amount_cents) for s in splits]
                if splits
                else [(tx.category_id, tx.amount_cents)]
            )
            for category_id, amount in allocations:
                category = categories.get(category_id)
                add_link(account_label, category.name if category else "Outros", amount)
            account_out[tx.account_id] = account_out.get(tx.account_id, 0) + tx.amount_cents

        elif tx.type == TransactionType.transfer:
            dest = accounts.get(tx.transfer_account_id)
            add_link(account_label, dest.name if dest else "Outra conta", tx.amount_cents)
            account_out[tx.account_id] = account_out.get(tx.account_id, 0) + tx.amount_cents

    for account_id, inflow in account_in.items():
        leftover = inflow - account_out.get(account_id, 0)
        if leftover > 0:
            account = accounts.get(account_id)
            add_link(account.name if account else "Conta", "Sobra", leftover)

    if not labels:
        return None

    return {
        "labels": labels,
        "source": [key[0] for key in links],
        "target": [key[1] for key in links],
        "value": [amount / 100 for amount in links.values()],
    }

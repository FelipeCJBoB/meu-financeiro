from __future__ import annotations

from datetime import date

from sqlmodel import Session

from app.models import Goal, TransactionType
from app.services.goals import list_goals
from app.services.money import month_bounds, month_key, month_key_for_date, months_between
from app.services.recurring import list_recurring_rules
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
    """Simplifi-style headline number: income - committed bills - goal pacing.

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
    committed_cents = totals["expense_cents"] + upcoming_expense_cents + goals_need_cents

    return {
        "income_total_cents": income_total_cents,
        "spent_cents": totals["expense_cents"],
        "upcoming_expense_cents": upcoming_expense_cents,
        "goals_need_cents": goals_need_cents,
        "committed_cents": committed_cents,
        "available_cents": income_total_cents - committed_cents,
    }

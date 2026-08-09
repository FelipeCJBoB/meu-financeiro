from __future__ import annotations

import math
from datetime import date

from sqlmodel import Session, select

from app.models import Goal, GoalContribution, GoalStatus


def list_goals(
    session: Session,
    *,
    include_archived: bool = False,
    status: GoalStatus | None = None,
) -> list[Goal]:
    stmt = select(Goal)
    if not include_archived:
        stmt = stmt.where(Goal.archived == False)  # noqa: E712
    if status is not None:
        stmt = stmt.where(Goal.status == status)
    return list(session.exec(stmt).all())


def create_goal(
    session: Session,
    *,
    name: str,
    target_amount_cents: int,
    icon: str = "flag",
    target_date: date | None = None,
    linked_account_id: int | None = None,
) -> Goal:
    goal = Goal(
        name=name,
        target_amount_cents=target_amount_cents,
        icon=icon,
        target_date=target_date,
        linked_account_id=linked_account_id,
    )
    session.add(goal)
    session.commit()
    session.refresh(goal)
    return goal


def update_goal(
    session: Session,
    goal_id: int,
    *,
    name: str | None = None,
    target_amount_cents: int | None = None,
    target_date: date | None = None,
    clear_target_date: bool = False,
    icon: str | None = None,
    status: GoalStatus | None = None,
) -> Goal:
    goal = session.get(Goal, goal_id)
    if goal is None:
        raise ValueError(f"Meta {goal_id} nao encontrada")
    if name is not None:
        goal.name = name
    if target_amount_cents is not None:
        goal.target_amount_cents = target_amount_cents
    if clear_target_date:
        goal.target_date = None
    elif target_date is not None:
        goal.target_date = target_date
    if icon is not None:
        goal.icon = icon
    if status is not None:
        goal.status = status
    session.add(goal)
    session.commit()
    session.refresh(goal)
    return goal


def delete_goal(session: Session, goal_id: int) -> None:
    for contribution in session.exec(
        select(GoalContribution).where(GoalContribution.goal_id == goal_id)
    ).all():
        session.delete(contribution)
    goal = session.get(Goal, goal_id)
    if goal:
        session.delete(goal)
    session.commit()


def contribute(
    session: Session,
    goal_id: int,
    amount_cents: int,
    *,
    on_date: date | None = None,
    note: str | None = None,
) -> Goal:
    goal = session.get(Goal, goal_id)
    if goal is None:
        raise ValueError(f"Meta {goal_id} nao encontrada")

    session.add(
        GoalContribution(
            goal_id=goal_id,
            date=on_date or date.today(),
            amount_cents=amount_cents,
            note=note,
        )
    )
    goal.current_amount_cents += amount_cents
    if goal.current_amount_cents >= goal.target_amount_cents > 0:
        goal.status = GoalStatus.completed
    session.add(goal)
    session.commit()
    session.refresh(goal)
    return goal


def list_contributions(session: Session, goal_id: int) -> list[GoalContribution]:
    return list(
        session.exec(
            select(GoalContribution)
            .where(GoalContribution.goal_id == goal_id)
            .order_by(GoalContribution.date.desc(), GoalContribution.id.desc())
        ).all()
    )


def delete_contribution(session: Session, contribution_id: int) -> None:
    contribution = session.get(GoalContribution, contribution_id)
    if contribution is None:
        return
    goal = session.get(Goal, contribution.goal_id)
    if goal:
        goal.current_amount_cents -= contribution.amount_cents
        if goal.status == GoalStatus.completed and goal.current_amount_cents < goal.target_amount_cents:
            goal.status = GoalStatus.active
        session.add(goal)
    session.delete(contribution)
    session.commit()


def progress_pct(goal: Goal) -> float:
    if goal.target_amount_cents <= 0:
        return 0.0
    return min(1.0, goal.current_amount_cents / goal.target_amount_cents)


def expected_progress_pct(goal: Goal, *, as_of: date | None = None) -> float | None:
    """Where the goal 'should' be today assuming linear pacing from creation to deadline."""
    if not goal.target_date:
        return None
    as_of = as_of or date.today()
    total_days = (goal.target_date - goal.created_at).days
    if total_days <= 0:
        return 1.0
    elapsed_days = (as_of - goal.created_at).days
    return max(0.0, min(1.0, elapsed_days / total_days))


def average_monthly_contribution_cents(session: Session, goal: Goal) -> int:
    """Observed pace, from the contribution log - not a guess."""
    contributions = list_contributions(session, goal.id)
    if not contributions:
        return 0
    first = min(c.date for c in contributions)
    months_span = max(1, ((date.today().year - first.year) * 12 + date.today().month - first.month) + 1)
    return round(sum(c.amount_cents for c in contributions) / months_span)


def months_to_target(session: Session, goal: Goal) -> int | None:
    """At the observed pace, how many months until the target is reached."""
    remaining = goal.target_amount_cents - goal.current_amount_cents
    if remaining <= 0:
        return 0
    pace = average_monthly_contribution_cents(session, goal)
    if pace <= 0:
        return None
    return math.ceil(remaining / pace)


def required_monthly_cents(goal: Goal, *, as_of: date | None = None) -> int | None:
    """How much per month is needed to land exactly on the deadline."""
    if not goal.target_date:
        return None
    as_of = as_of or date.today()
    remaining = goal.target_amount_cents - goal.current_amount_cents
    if remaining <= 0:
        return 0
    months_left = (goal.target_date.year - as_of.year) * 12 + (goal.target_date.month - as_of.month)
    months_left = max(1, months_left)
    return round(remaining / months_left)


def progress_series(session: Session, goal: Goal) -> dict:
    """Actual accumulated progress over time vs. the straight line to the deadline."""
    contributions = sorted(list_contributions(session, goal.id), key=lambda c: c.date)
    actual_dates = [goal.created_at]
    actual_values = [0]
    running = 0
    for contribution in contributions:
        running += contribution.amount_cents
        actual_dates.append(contribution.date)
        actual_values.append(running)

    today = date.today()
    if actual_dates[-1] < today:
        actual_dates.append(today)
        actual_values.append(running)

    planned_dates: list[date] = []
    planned_values: list[int] = []
    if goal.target_date:
        planned_dates = [goal.created_at, goal.target_date]
        planned_values = [0, goal.target_amount_cents]

    return {
        "actual_dates": actual_dates,
        "actual_values": actual_values,
        "planned_dates": planned_dates,
        "planned_values": planned_values,
    }

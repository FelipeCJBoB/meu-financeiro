from __future__ import annotations

from datetime import date

from sqlmodel import Session, select

from app.models import Goal


def list_goals(session: Session, *, include_archived: bool = False) -> list[Goal]:
    stmt = select(Goal)
    if not include_archived:
        stmt = stmt.where(Goal.archived == False)  # noqa: E712
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


def contribute(session: Session, goal_id: int, amount_cents: int) -> Goal:
    goal = session.get(Goal, goal_id)
    if goal is None:
        raise ValueError(f"Meta {goal_id} nao encontrada")
    goal.current_amount_cents += amount_cents
    session.add(goal)
    session.commit()
    session.refresh(goal)
    return goal


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

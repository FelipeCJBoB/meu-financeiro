from __future__ import annotations

from datetime import date, timedelta

from sqlmodel import Session, select

from app.models import RecurringRule, Transaction
from app.services.money import add_months
from app.services.transactions import create_transaction


def create_recurring_rule(
    session: Session,
    *,
    description: str,
    account_id: int,
    type_,
    amount_cents: int,
    frequency,
    next_due_date: date,
    category_id: int | None = None,
) -> RecurringRule:
    rule = RecurringRule(
        description=description,
        account_id=account_id,
        category_id=category_id,
        type=type_,
        amount_cents=amount_cents,
        frequency=frequency,
        next_due_date=next_due_date,
    )
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


def list_recurring_rules(session: Session, *, active_only: bool = True) -> list[RecurringRule]:
    stmt = select(RecurringRule)
    if active_only:
        stmt = stmt.where(RecurringRule.active == True)  # noqa: E712
    return list(session.exec(stmt.order_by(RecurringRule.next_due_date)).all())


def due_recurring_rules(session: Session, *, as_of: date | None = None) -> list[RecurringRule]:
    as_of = as_of or date.today()
    return list(
        session.exec(
            select(RecurringRule).where(
                RecurringRule.active == True,  # noqa: E712
                RecurringRule.next_due_date <= as_of,
            )
        ).all()
    )


def upcoming_recurring_rules(
    session: Session, *, within_days: int = 30, as_of: date | None = None
) -> list[RecurringRule]:
    """Active rules due in the future within the window - not yet overdue."""
    as_of = as_of or date.today()
    horizon = as_of + timedelta(days=within_days)
    return list(
        session.exec(
            select(RecurringRule)
            .where(
                RecurringRule.active == True,  # noqa: E712
                RecurringRule.next_due_date > as_of,
                RecurringRule.next_due_date <= horizon,
            )
            .order_by(RecurringRule.next_due_date)
        ).all()
    )


def advance_date(d: date, frequency) -> date:
    value = frequency.value if hasattr(frequency, "value") else frequency
    if value == "weekly":
        return d + timedelta(days=7)
    if value == "monthly":
        return add_months(d, 1)
    return add_months(d, 12)


def confirm_recurring(
    session: Session, rule_id: int, *, amount_cents: int | None = None
) -> Transaction:
    rule = session.get(RecurringRule, rule_id)
    if rule is None:
        raise ValueError(f"Regra recorrente {rule_id} nao encontrada")

    transaction = create_transaction(
        session,
        date_=rule.next_due_date,
        description=rule.description,
        account_id=rule.account_id,
        type_=rule.type,
        amount_cents=amount_cents if amount_cents is not None else rule.amount_cents,
        category_id=rule.category_id,
        recurring_rule_id=rule.id,
    )

    rule.next_due_date = advance_date(rule.next_due_date, rule.frequency)
    session.add(rule)
    session.commit()
    return transaction


def skip_recurring(session: Session, rule_id: int) -> None:
    rule = session.get(RecurringRule, rule_id)
    if rule is None:
        return
    rule.next_due_date = advance_date(rule.next_due_date, rule.frequency)
    session.add(rule)
    session.commit()

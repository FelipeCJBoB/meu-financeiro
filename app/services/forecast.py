from __future__ import annotations

from datetime import date, timedelta

from sqlmodel import Session

from app.models import TransactionType
from app.services.networth import current_net_worth
from app.services.recurring import advance_date, list_recurring_rules


def project_net_worth(session: Session, *, horizon_days: int = 90) -> list[tuple[date, int]]:
    """Projects net worth forward using only scheduled recurring income/expense rules.

    Transfers and adjustments are excluded on purpose: they move money between the
    user's own accounts (or correct a manual balance) and do not change total net worth.
    This is a floor/ceiling based on known commitments, not a prediction of ad-hoc spending.
    """
    today = date.today()
    horizon_end = today + timedelta(days=horizon_days)
    current_total, _ = current_net_worth(session)

    events: list[tuple[date, int]] = []
    for rule in list_recurring_rules(session, active_only=True):
        if rule.type not in (TransactionType.income, TransactionType.expense):
            continue
        sign = 1 if rule.type == TransactionType.income else -1
        occurrence = rule.next_due_date
        guard = 0
        while occurrence <= horizon_end and guard < 500:
            events.append((occurrence, sign * rule.amount_cents))
            occurrence = advance_date(occurrence, rule.frequency)
            guard += 1

    events.sort(key=lambda item: item[0])

    series = [(today, current_total)]
    running = current_total
    for event_date, delta in events:
        running += delta
        series.append((event_date, running))
    return series

from __future__ import annotations

import json
from datetime import date

from sqlmodel import Session, select

from app.models import Account, NetWorthSnapshot
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

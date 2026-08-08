from __future__ import annotations

from sqlmodel import Session, select

from app.models import Account, AccountType, Transaction, TransactionType


def list_accounts(session: Session, *, include_archived: bool = False) -> list[Account]:
    stmt = select(Account)
    if not include_archived:
        stmt = stmt.where(Account.archived == False)  # noqa: E712
    return list(session.exec(stmt.order_by(Account.name)).all())


def create_account(
    session: Session,
    *,
    name: str,
    type: AccountType,
    initial_balance_cents: int = 0,
) -> Account:
    account = Account(name=name, type=type, initial_balance_cents=initial_balance_cents)
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


def account_balance_cents(session: Session, account_id: int) -> int:
    account = session.get(Account, account_id)
    if account is None:
        raise ValueError(f"Conta {account_id} nao encontrada")

    total = account.initial_balance_cents

    outgoing = session.exec(select(Transaction).where(Transaction.account_id == account_id)).all()
    for tx in outgoing:
        if tx.type == TransactionType.income:
            total += tx.amount_cents
        elif tx.type == TransactionType.expense:
            total -= tx.amount_cents
        elif tx.type == TransactionType.transfer:
            total -= tx.amount_cents
        elif tx.type == TransactionType.adjustment:
            total += tx.amount_cents

    incoming = session.exec(
        select(Transaction).where(
            Transaction.transfer_account_id == account_id,
            Transaction.type == TransactionType.transfer,
        )
    ).all()
    for tx in incoming:
        total += tx.amount_cents

    return total


def adjust_balance(session: Session, account_id: int, new_balance_cents: int, *, description: str = "Ajuste de saldo") -> Transaction:
    from app.services.transactions import create_transaction
    from datetime import date as date_cls

    current = account_balance_cents(session, account_id)
    delta = new_balance_cents - current
    return create_transaction(
        session,
        date_=date_cls.today(),
        description=description,
        account_id=account_id,
        type_=TransactionType.adjustment,
        amount_cents=delta,
    )

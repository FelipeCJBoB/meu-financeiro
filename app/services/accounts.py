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


def update_account(
    session: Session,
    account_id: int,
    *,
    name: str | None = None,
    type: AccountType | None = None,
) -> Account:
    account = session.get(Account, account_id)
    if account is None:
        raise ValueError(f"Conta {account_id} nao encontrada")
    if name is not None:
        account.name = name
    if type is not None:
        account.type = type
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


def set_archived(session: Session, account_id: int, archived: bool) -> Account:
    account = session.get(Account, account_id)
    if account is None:
        raise ValueError(f"Conta {account_id} nao encontrada")
    account.archived = archived
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


def transaction_count(session: Session, account_id: int) -> int:
    own = session.exec(select(Transaction).where(Transaction.account_id == account_id)).all()
    incoming = session.exec(
        select(Transaction).where(Transaction.transfer_account_id == account_id)
    ).all()
    return len(own) + len(incoming)


def delete_account(session: Session, account_id: int, *, cascade: bool = False) -> None:
    """Removes an account. Refuses to silently orphan history: without cascade,
    an account that still has transactions raises instead of deleting."""
    from app.services.transactions import delete_transaction

    account = session.get(Account, account_id)
    if account is None:
        return

    related = session.exec(select(Transaction).where(Transaction.account_id == account_id)).all()
    incoming = session.exec(
        select(Transaction).where(Transaction.transfer_account_id == account_id)
    ).all()
    all_related = {tx.id: tx for tx in list(related) + list(incoming)}

    if all_related and not cascade:
        raise ValueError(
            f"A conta tem {len(all_related)} lancamentos. Arquive a conta ou confirme a "
            f"exclusao junto com o historico."
        )

    for tx_id in all_related:
        delete_transaction(session, tx_id)

    session.delete(account)
    session.commit()


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

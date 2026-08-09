from __future__ import annotations

from sqlmodel import Session, select

from app.models import Account, AccountType, Goal, RecurringRule, Transaction, TransactionType


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


def account_references(session: Session, account_id: int) -> dict:
    """Everything that points at this account. Foreign keys are enforced, so any
    of these left behind makes the delete fail at the database level."""
    own = session.exec(select(Transaction).where(Transaction.account_id == account_id)).all()
    incoming = session.exec(
        select(Transaction).where(Transaction.transfer_account_id == account_id)
    ).all()
    rules = session.exec(
        select(RecurringRule).where(RecurringRule.account_id == account_id)
    ).all()
    goals = session.exec(select(Goal).where(Goal.linked_account_id == account_id)).all()
    return {
        "transactions": {tx.id: tx for tx in list(own) + list(incoming)},
        "recurring_rules": list(rules),
        "goals": list(goals),
    }


def delete_account(session: Session, account_id: int, *, cascade: bool = False) -> None:
    """Removes an account. Refuses to silently orphan history: without cascade,
    an account that is still referenced raises instead of deleting."""
    from app.services.transactions import delete_transaction

    account = session.get(Account, account_id)
    if account is None:
        return

    refs = account_references(session, account_id)
    total_refs = (
        len(refs["transactions"]) + len(refs["recurring_rules"]) + len(refs["goals"])
    )

    if total_refs and not cascade:
        raise ValueError(
            f"A conta tem {len(refs['transactions'])} lancamento(s) e "
            f"{len(refs['recurring_rules'])} recorrencia(s). Arquive a conta ou confirme "
            f"a exclusao junto com esse historico."
        )

    for tx_id in refs["transactions"]:
        delete_transaction(session, tx_id)

    for rule in refs["recurring_rules"]:
        session.delete(rule)

    for goal in refs["goals"]:
        goal.linked_account_id = None
        session.add(goal)

    # Commit the dependents first: without declared relationships SQLAlchemy has no
    # dependency graph and may emit the account DELETE before these, tripping the
    # foreign key constraint.
    session.commit()

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

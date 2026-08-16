from __future__ import annotations

from datetime import date

from sqlmodel import Session, and_, or_, select

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


def account_balance_cents(session: Session, account_id: int, *, as_of: date | None = None) -> int:
    """Current balance: the last confirmed "Ajustar saldo" plus every real money
    movement dated strictly after it, up to `as_of` (today by default).

    A transaction dated on or before that last sync is treated as something the
    real-world balance the user typed in already accounts for - logging a bill
    afterwards, just to categorize it, must not subtract it a second time.
    Summing every transaction regardless of date, the old behaviour, double
    counted every such backdated entry. Anything dated after `as_of` (a bill
    pre-logged for later this month) is future activity that has not left the
    account yet, so it is excluded too, the same way an unconfirmed recurring
    charge does not touch the balance until it is actually paid.

    already_settled overrides both rules by hand: a transaction marked that way
    never affects the balance, no matter its date, for the cases the anchor
    cannot infer on its own (no adjustment yet, or one older than this entry).
    """
    if as_of is None:
        as_of = date.today()

    account = session.get(Account, account_id)
    if account is None:
        raise ValueError(f"Conta {account_id} nao encontrada")

    anchor = session.exec(
        select(Transaction)
        .where(
            Transaction.account_id == account_id,
            Transaction.type == TransactionType.adjustment,
            Transaction.balance_after_cents.is_not(None),
            Transaction.date <= as_of,
        )
        .order_by(Transaction.date.desc(), Transaction.id.desc())
    ).first()

    if anchor is not None:
        total = anchor.balance_after_cents
        # Same-day entries need a second, id-based tiebreak: a purchase logged
        # today after the sync is new activity and must count, but the sync
        # itself (and anything dated before it) is already baked into the
        # anchor value above.
        after_anchor = or_(
            Transaction.date > anchor.date,
            and_(Transaction.date == anchor.date, Transaction.id > anchor.id),
        )
    else:
        total = account.initial_balance_cents
        after_anchor = None

    stmt = select(Transaction).where(
        Transaction.account_id == account_id,
        Transaction.date <= as_of,
        Transaction.already_settled == False,  # noqa: E712
    )
    if after_anchor is not None:
        stmt = stmt.where(after_anchor)
    for tx in session.exec(stmt).all():
        if tx.type == TransactionType.income:
            total += tx.amount_cents
        elif tx.type == TransactionType.expense:
            total -= tx.amount_cents
        elif tx.type == TransactionType.transfer:
            total -= tx.amount_cents
        elif tx.type == TransactionType.adjustment:
            total += tx.amount_cents

    incoming_stmt = select(Transaction).where(
        Transaction.transfer_account_id == account_id,
        Transaction.type == TransactionType.transfer,
        Transaction.date <= as_of,
        Transaction.already_settled == False,  # noqa: E712
    )
    if after_anchor is not None:
        incoming_stmt = incoming_stmt.where(after_anchor)
    for tx in session.exec(incoming_stmt).all():
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

    today = date.today()
    current = account_balance_cents(session, account_id, as_of=today)
    delta = new_balance_cents - current
    return create_transaction(
        session,
        date_=today,
        description=description,
        account_id=account_id,
        type_=TransactionType.adjustment,
        amount_cents=delta,
        # The anchor account_balance_cents() rebuilds from next time - stored
        # as the absolute value so a later backdated insert can't erode it the
        # way relying only on the delta above did.
        balance_after_cents=new_balance_cents,
    )

from __future__ import annotations

from datetime import date

from sqlmodel import Session, select

from app.models import Transaction, TransactionSplit, TransactionType
from app.services.money import month_bounds, previous_month


class TransactionError(ValueError):
    pass


def create_transaction(
    session: Session,
    *,
    date_: date,
    description: str,
    account_id: int,
    type_: TransactionType,
    amount_cents: int,
    category_id: int | None = None,
    transfer_account_id: int | None = None,
    splits: list[dict] | None = None,
    tags: str | None = None,
    notes: str | None = None,
    recurring_rule_id: int | None = None,
) -> Transaction:
    if type_ == TransactionType.transfer:
        if not transfer_account_id:
            raise TransactionError("Transferencia precisa de uma conta de destino")
        if transfer_account_id == account_id:
            raise TransactionError("Conta de origem e destino nao podem ser iguais")
        category_id = None
    elif type_ != TransactionType.adjustment and category_id is None and not splits:
        raise TransactionError("Informe uma categoria ou divida o lancamento")

    if splits:
        total_split = sum(item["amount_cents"] for item in splits)
        if total_split != amount_cents:
            raise TransactionError("A soma das divisoes deve ser igual ao valor total")
        category_id = None

    transaction = Transaction(
        date=date_,
        description=description,
        account_id=account_id,
        type=type_,
        amount_cents=amount_cents,
        category_id=category_id,
        transfer_account_id=transfer_account_id,
        tags=tags,
        notes=notes,
        recurring_rule_id=recurring_rule_id,
    )
    session.add(transaction)
    session.commit()
    session.refresh(transaction)

    if splits:
        for item in splits:
            session.add(
                TransactionSplit(
                    transaction_id=transaction.id,
                    category_id=item["category_id"],
                    amount_cents=item["amount_cents"],
                )
            )
        session.commit()

    return transaction


def update_transaction(
    session: Session,
    transaction_id: int,
    *,
    date_: date,
    description: str,
    account_id: int,
    type_: TransactionType,
    amount_cents: int,
    category_id: int | None = None,
    transfer_account_id: int | None = None,
    splits: list[dict] | None = None,
    notes: str | None = None,
) -> Transaction:
    transaction = session.get(Transaction, transaction_id)
    if transaction is None:
        raise TransactionError("Lancamento nao encontrado")

    if type_ == TransactionType.transfer:
        if not transfer_account_id:
            raise TransactionError("Transferencia precisa de uma conta de destino")
        if transfer_account_id == account_id:
            raise TransactionError("Conta de origem e destino nao podem ser iguais")
        category_id = None
    elif type_ != TransactionType.adjustment and category_id is None and not splits:
        raise TransactionError("Informe uma categoria ou divida o lancamento")

    if splits:
        total_split = sum(item["amount_cents"] for item in splits)
        if total_split != amount_cents:
            raise TransactionError("A soma das divisoes deve ser igual ao valor total")
        category_id = None

    transaction.date = date_
    transaction.description = description
    transaction.account_id = account_id
    transaction.type = type_
    transaction.amount_cents = amount_cents
    transaction.category_id = category_id
    transaction.transfer_account_id = (
        transfer_account_id if type_ == TransactionType.transfer else None
    )
    if notes is not None:
        transaction.notes = notes
    session.add(transaction)

    existing_splits = session.exec(
        select(TransactionSplit).where(TransactionSplit.transaction_id == transaction_id)
    ).all()
    for split in existing_splits:
        session.delete(split)
    if splits:
        for item in splits:
            session.add(
                TransactionSplit(
                    transaction_id=transaction_id,
                    category_id=item["category_id"],
                    amount_cents=item["amount_cents"],
                )
            )

    session.commit()
    session.refresh(transaction)
    return transaction


def delete_transaction(session: Session, transaction_id: int) -> None:
    splits = session.exec(
        select(TransactionSplit).where(TransactionSplit.transaction_id == transaction_id)
    ).all()
    for split in splits:
        session.delete(split)
    transaction = session.get(Transaction, transaction_id)
    if transaction:
        session.delete(transaction)
    session.commit()


def list_transactions(
    session: Session,
    *,
    account_id: int | None = None,
    category_id: int | None = None,
    start: date | None = None,
    end: date | None = None,
    limit: int | None = None,
) -> list[Transaction]:
    stmt = select(Transaction)
    if account_id is not None:
        stmt = stmt.where(Transaction.account_id == account_id)
    if category_id is not None:
        stmt = stmt.where(Transaction.category_id == category_id)
    if start is not None:
        stmt = stmt.where(Transaction.date >= start)
    if end is not None:
        stmt = stmt.where(Transaction.date <= end)
    stmt = stmt.order_by(Transaction.date.desc(), Transaction.id.desc())
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(session.exec(stmt).all())


def month_totals(session: Session, month: str, cycle_start_day: int = 1) -> dict:
    start, end = month_bounds(month, cycle_start_day)
    incomes = session.exec(
        select(Transaction).where(
            Transaction.type == TransactionType.income,
            Transaction.date >= start,
            Transaction.date <= end,
        )
    ).all()
    expenses = session.exec(
        select(Transaction).where(
            Transaction.type == TransactionType.expense,
            Transaction.date >= start,
            Transaction.date <= end,
        )
    ).all()
    return {
        "income_cents": sum(tx.amount_cents for tx in incomes),
        "expense_cents": sum(tx.amount_cents for tx in expenses),
    }


def range_totals(session: Session, start: date, end: date) -> dict:
    incomes = session.exec(
        select(Transaction).where(
            Transaction.type == TransactionType.income,
            Transaction.date >= start,
            Transaction.date <= end,
        )
    ).all()
    expenses = session.exec(
        select(Transaction).where(
            Transaction.type == TransactionType.expense,
            Transaction.date >= start,
            Transaction.date <= end,
        )
    ).all()
    return {
        "income_cents": sum(tx.amount_cents for tx in incomes),
        "expense_cents": sum(tx.amount_cents for tx in expenses),
    }


def monthly_series(
    session: Session, *, end_month: str, months: int = 6, cycle_start_day: int = 1
) -> list[dict]:
    month_labels = [end_month]
    for _ in range(months - 1):
        month_labels.append(previous_month(month_labels[-1]))
    month_labels.reverse()

    return [
        {"month": m, **month_totals(session, m, cycle_start_day)} for m in month_labels
    ]


def transaction_splits(session: Session, transaction_id: int) -> list[TransactionSplit]:
    return list(
        session.exec(
            select(TransactionSplit).where(TransactionSplit.transaction_id == transaction_id)
        ).all()
    )

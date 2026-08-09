from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from sqlmodel import Field, SQLModel, UniqueConstraint


class AccountType(str, Enum):
    checking = "checking"
    savings = "savings"
    credit_card = "credit_card"
    investment = "investment"
    physical_asset = "physical_asset"
    loan = "loan"
    other = "other"


LIABILITY_TYPES = {AccountType.credit_card, AccountType.loan}
LIQUID_TYPES = {AccountType.checking, AccountType.savings}


class GoalStatus(str, Enum):
    active = "active"
    paused = "paused"
    completed = "completed"


class CategoryKind(str, Enum):
    income = "income"
    expense = "expense"
    both = "both"


class TransactionType(str, Enum):
    income = "income"
    expense = "expense"
    transfer = "transfer"
    adjustment = "adjustment"


class Frequency(str, Enum):
    weekly = "weekly"
    monthly = "monthly"
    yearly = "yearly"


class Account(SQLModel, table=True):
    __tablename__ = "accounts"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    type: AccountType
    initial_balance_cents: int = 0
    archived: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Category(SQLModel, table=True):
    __tablename__ = "categories"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    icon: str = "sell"
    color: str = "#8ab4e8"
    kind: CategoryKind = CategoryKind.expense
    parent_id: int | None = Field(default=None, foreign_key="categories.id")
    archived: bool = False


class CategoryRule(SQLModel, table=True):
    __tablename__ = "category_rules"

    id: int | None = Field(default=None, primary_key=True)
    match_text: str
    category_id: int = Field(foreign_key="categories.id")


class RecurringRule(SQLModel, table=True):
    __tablename__ = "recurring_rules"

    id: int | None = Field(default=None, primary_key=True)
    description: str
    account_id: int = Field(foreign_key="accounts.id")
    category_id: int | None = Field(default=None, foreign_key="categories.id")
    type: TransactionType
    amount_cents: int
    frequency: Frequency
    day_of_month: int | None = None
    weekday: int | None = None
    next_due_date: date
    active: bool = True


class Transaction(SQLModel, table=True):
    __tablename__ = "transactions"

    id: int | None = Field(default=None, primary_key=True)
    date: date
    description: str
    amount_cents: int
    type: TransactionType
    account_id: int = Field(foreign_key="accounts.id")
    category_id: int | None = Field(default=None, foreign_key="categories.id")
    transfer_account_id: int | None = Field(default=None, foreign_key="accounts.id")
    recurring_rule_id: int | None = Field(default=None, foreign_key="recurring_rules.id")
    tags: str | None = None
    notes: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TransactionSplit(SQLModel, table=True):
    __tablename__ = "transaction_splits"

    id: int | None = Field(default=None, primary_key=True)
    transaction_id: int = Field(foreign_key="transactions.id")
    category_id: int = Field(foreign_key="categories.id")
    amount_cents: int


class Budget(SQLModel, table=True):
    __tablename__ = "budgets"
    __table_args__ = (UniqueConstraint("category_id", "month"),)

    id: int | None = Field(default=None, primary_key=True)
    category_id: int = Field(foreign_key="categories.id")
    month: str
    amount_cents: int


class Goal(SQLModel, table=True):
    __tablename__ = "goals"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    icon: str = "flag"
    target_amount_cents: int
    current_amount_cents: int = 0
    target_date: date | None = None
    linked_account_id: int | None = Field(default=None, foreign_key="accounts.id")
    archived: bool = False
    created_at: date = Field(default_factory=date.today)
    status: GoalStatus = GoalStatus.active


class GoalContribution(SQLModel, table=True):
    __tablename__ = "goal_contributions"

    id: int | None = Field(default=None, primary_key=True)
    goal_id: int = Field(foreign_key="goals.id")
    date: date
    amount_cents: int
    note: str | None = None


class NetWorthSnapshot(SQLModel, table=True):
    __tablename__ = "net_worth_snapshots"

    id: int | None = Field(default=None, primary_key=True)
    date: date
    net_worth_cents: int
    breakdown_json: str


class Settings(SQLModel, table=True):
    __tablename__ = "settings"

    id: int | None = Field(default=1, primary_key=True)
    cycle_start_day: int = 1
    window_width: int = 2560
    window_height: int = 1440
    theme_name: str = "linen"

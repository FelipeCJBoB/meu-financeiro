from __future__ import annotations

from sqlmodel import Session, select

from app.models import Category, CategoryKind, CategoryRule


def list_categories(session: Session, *, include_archived: bool = False) -> list[Category]:
    stmt = select(Category)
    if not include_archived:
        stmt = stmt.where(Category.archived == False)  # noqa: E712
    return list(session.exec(stmt.order_by(Category.name)).all())


def get_or_create_category(
    session: Session,
    *,
    name: str,
    icon: str = "ti-tag",
    color: str = "#8ab4e8",
    kind: CategoryKind = CategoryKind.expense,
    parent_id: int | None = None,
) -> Category:
    name = name.strip()
    existing = session.exec(
        select(Category).where(
            Category.name.ilike(name),
            Category.parent_id == parent_id,
        )
    ).first()
    if existing:
        return existing

    category = Category(name=name, icon=icon, color=color, kind=kind, parent_id=parent_id)
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


def archive_category(session: Session, category_id: int) -> None:
    category = session.get(Category, category_id)
    if category is None:
        return
    category.archived = True
    session.add(category)
    session.commit()


def children_of(session: Session, parent_id: int | None) -> list[Category]:
    return list(
        session.exec(
            select(Category).where(Category.parent_id == parent_id, Category.archived == False)  # noqa: E712
        ).all()
    )


def add_rule(session: Session, *, match_text: str, category_id: int) -> CategoryRule:
    rule = CategoryRule(match_text=match_text.strip().lower(), category_id=category_id)
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


def suggest_category(session: Session, description: str) -> Category | None:
    if not description:
        return None
    desc_lower = description.lower()
    rules = session.exec(select(CategoryRule)).all()
    for rule in rules:
        if rule.match_text in desc_lower:
            return session.get(Category, rule.category_id)
    return None

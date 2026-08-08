from __future__ import annotations

from sqlmodel import Session

from app.models import Settings


def get_settings(session: Session) -> Settings:
    settings = session.get(Settings, 1)
    if settings is None:
        settings = Settings(id=1, cycle_start_day=1)
        session.add(settings)
        session.commit()
        session.refresh(settings)
    return settings


def set_cycle_start_day(session: Session, day: int) -> Settings:
    day = max(1, min(31, day))
    settings = get_settings(session)
    settings.cycle_start_day = day
    session.add(settings)
    session.commit()
    session.refresh(settings)
    return settings

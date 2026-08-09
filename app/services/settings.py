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


def set_theme_name(session: Session, name: str) -> Settings:
    settings = get_settings(session)
    settings.theme_name = name
    session.add(settings)
    session.commit()
    session.refresh(settings)
    return settings


def backup_database(destination_dir: str | None = None) -> str:
    """Copies the SQLite file (WAL checkpointed first) to a timestamped backup.

    All the user's history lives in a single file; a one-click copy is the
    cheapest possible protection against losing years of records.
    """
    import shutil
    from datetime import datetime
    from pathlib import Path

    from sqlalchemy import text

    from app.db import DB_PATH, engine

    with engine.connect() as conn:
        conn.execute(text("PRAGMA wal_checkpoint(FULL)"))
        conn.commit()

    target_dir = Path(destination_dir) if destination_dir else DB_PATH.parent / "backups"
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = target_dir / f"dados-{stamp}.db"
    shutil.copy2(DB_PATH, target)
    return str(target)


def set_window_size(session: Session, width: int, height: int) -> Settings:
    settings = get_settings(session)
    settings.window_width = width
    settings.window_height = height
    session.add(settings)
    session.commit()
    session.refresh(settings)
    return settings

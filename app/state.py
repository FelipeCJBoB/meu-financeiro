from __future__ import annotations

from datetime import date

from app.services.money import add_months, month_key, month_key_for_date

_state: dict = {"month": None, "cycle_start_day": None}


def _ensure_loaded() -> None:
    if _state["cycle_start_day"] is None:
        from app.db import get_session
        from app.services import settings as settings_service

        with get_session() as session:
            _state["cycle_start_day"] = settings_service.get_settings(session).cycle_start_day
    if _state["month"] is None:
        _state["month"] = month_key_for_date(date.today(), _state["cycle_start_day"])


def cycle_start_day() -> int:
    _ensure_loaded()
    return _state["cycle_start_day"]


def set_cycle_start_day(day: int) -> None:
    from app.db import get_session
    from app.services import settings as settings_service

    with get_session() as session:
        settings_service.set_cycle_start_day(session, day)
    _state["cycle_start_day"] = day
    _state["month"] = month_key_for_date(date.today(), day)


def current_month() -> str:
    _ensure_loaded()
    return _state["month"]


def set_month(month: str) -> None:
    _state["month"] = month


def shift_month(delta: int) -> str:
    _ensure_loaded()
    year, month_num = (int(part) for part in _state["month"].split("-"))
    shifted = add_months(date(year, month_num, 1), delta)
    _state["month"] = month_key(shifted)
    return _state["month"]


def is_current_cycle() -> bool:
    _ensure_loaded()
    return _state["month"] == month_key_for_date(date.today(), _state["cycle_start_day"])


def reset_to_today() -> None:
    _ensure_loaded()
    _state["month"] = month_key_for_date(date.today(), _state["cycle_start_day"])


def window_size() -> tuple[int, int]:
    from app.db import get_session
    from app.services import settings as settings_service

    with get_session() as session:
        settings = settings_service.get_settings(session)
        return settings.window_width, settings.window_height


def set_window_size(width: int, height: int) -> None:
    from app.db import get_session
    from app.services import settings as settings_service

    with get_session() as session:
        settings_service.set_window_size(session, width, height)

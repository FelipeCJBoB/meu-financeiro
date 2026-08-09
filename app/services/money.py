from __future__ import annotations

import calendar
from datetime import date, timedelta


def to_cents(reais: float) -> int:
    return round(reais * 100)


def to_reais(cents: int) -> float:
    return cents / 100


def format_brl(cents: int) -> str:
    reais = cents / 100
    sign = "-" if reais < 0 else ""
    text = f"{abs(reais):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{sign}R$ {text}"


def month_key(d: date) -> str:
    return d.strftime("%Y-%m")


def add_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _cycle_start_date(year: int, month_num: int, cycle_start_day: int) -> date:
    day = min(cycle_start_day, calendar.monthrange(year, month_num)[1])
    return date(year, month_num, day)


def month_bounds(month: str, cycle_start_day: int = 1) -> tuple[date, date]:
    """Bounds of a financial cycle. cycle_start_day=1 is a plain calendar month."""
    year, month_num = (int(part) for part in month.split("-"))
    start = _cycle_start_date(year, month_num, cycle_start_day)
    next_month_first = add_months(date(year, month_num, 1), 1)
    next_start = _cycle_start_date(next_month_first.year, next_month_first.month, cycle_start_day)
    return start, next_start - timedelta(days=1)


def month_key_for_date(d: date, cycle_start_day: int = 1) -> str:
    """Which financial-cycle label a given date falls into."""
    if cycle_start_day <= 1:
        return month_key(d)
    start_this_cycle = _cycle_start_date(d.year, d.month, cycle_start_day)
    if d >= start_this_cycle:
        return month_key(d)
    prev = add_months(date(d.year, d.month, 1), -1)
    return month_key(prev)


def previous_month(month: str) -> str:
    year, month_num = (int(part) for part in month.split("-"))
    return month_key(add_months(date(year, month_num, 1), -1))


PERIOD_MONTHS = {"month": 1, "3m": 3, "12m": 12, "all": 120}
PERIOD_LABELS = {"month": "Mês", "3m": "3 meses", "12m": "12 meses", "all": "Tudo"}


def period_bounds(period: str, month: str, cycle_start_day: int = 1) -> tuple[date, date]:
    """Date range covered by a period selection, anchored on the cycle being viewed."""
    months = PERIOD_MONTHS.get(period, 1)
    _, end = month_bounds(month, cycle_start_day)
    year, month_num = (int(part) for part in month.split("-"))
    first_month = add_months(date(year, month_num, 1), -(months - 1))
    start, _ = month_bounds(month_key(first_month), cycle_start_day)
    return start, end


def months_between(month_a: str, month_b: str) -> int:
    year_a, num_a = (int(part) for part in month_a.split("-"))
    year_b, num_b = (int(part) for part in month_b.split("-"))
    return (year_b - year_a) * 12 + (num_b - num_a)


MONTH_NAMES_PT = [
    "Janeiro", "Fevereiro", "Marco", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]


def format_month_label(month: str) -> str:
    year, month_num = (int(part) for part in month.split("-"))
    return f"{MONTH_NAMES_PT[month_num - 1]} {year}"

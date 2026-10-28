"""Aritmética de meses. Um "mês" é representado pela data do seu primeiro dia."""

import calendar
from datetime import date


def first_day(value: date) -> date:
    return value.replace(day=1)


def add_months(month: date, count: int) -> date:
    """Primeiro dia do mês `count` meses depois de `month` (aceita valores negativos)."""
    index = month.year * 12 + month.month - 1 + count
    return date(index // 12, index % 12 + 1, 1)


def clamp_day(month: date, day: int) -> date:
    """Data no mês com o dia limitado ao último dia (dia 31 em abril vira 30)."""
    last_day = calendar.monthrange(month.year, month.month)[1]
    return date(month.year, month.month, min(day, last_day))


def month_bounds(month: date) -> tuple[date, date]:
    """Intervalo [início, fim) do mês."""
    start = first_day(month)
    return start, add_months(start, 1)


def months_between(start: date, end: date) -> int:
    """Quantidade de viradas de mês entre `start` e `end` (negativa se `end` vier antes)."""
    return (end.year - start.year) * 12 + end.month - start.month


def format_month(month: date) -> str:
    return f"{month.year:04d}-{month.month:02d}"

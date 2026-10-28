"""Ocorrências mensais de receitas e despesas fixas."""

from datetime import date

from financeiro.domain.months import clamp_day, first_day


def occurs_in(start_month: date, end_month: date | None, month: date) -> bool:
    month = first_day(month)
    return start_month <= month and (end_month is None or month <= end_month)


def occurrence_date(month: date, day_of_month: int) -> date:
    return clamp_day(month, day_of_month)

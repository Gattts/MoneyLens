from datetime import date

import pytest

from financeiro.domain.months import (
    add_months,
    clamp_day,
    first_day,
    format_month,
    month_bounds,
    months_between,
)


@pytest.mark.parametrize(
    ("month", "count", "expected"),
    [
        (date(2026, 10, 1), 1, date(2026, 11, 1)),
        (date(2026, 12, 1), 1, date(2027, 1, 1)),
        (date(2026, 1, 1), -1, date(2025, 12, 1)),
        (date(2026, 3, 1), -14, date(2025, 1, 1)),
        (date(2026, 10, 15), 2, date(2026, 12, 1)),
    ],
)
def test_add_months_returns_first_day_and_rolls_over_years(month, count, expected):
    assert add_months(month, count) == expected


@pytest.mark.parametrize(
    ("month", "day", "expected"),
    [
        (date(2026, 4, 1), 31, date(2026, 4, 30)),
        (date(2024, 2, 1), 31, date(2024, 2, 29)),
        (date(2026, 2, 1), 30, date(2026, 2, 28)),
        (date(2026, 10, 1), 5, date(2026, 10, 5)),
    ],
)
def test_clamp_day_limits_to_last_day_of_month(month, day, expected):
    assert clamp_day(month, day) == expected


def test_month_bounds_is_half_open_and_crosses_year():
    assert month_bounds(date(2026, 12, 10)) == (date(2026, 12, 1), date(2027, 1, 1))


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        (date(2026, 10, 1), date(2027, 3, 1), 5),
        (date(2026, 10, 31), date(2026, 10, 1), 0),
        (date(2027, 1, 1), date(2026, 11, 15), -2),
    ],
)
def test_months_between_counts_month_turns(start, end, expected):
    assert months_between(start, end) == expected


def test_format_month_and_first_day():
    assert format_month(date(2026, 3, 9)) == "2026-03"
    assert first_day(date(2026, 10, 27)) == date(2026, 10, 1)

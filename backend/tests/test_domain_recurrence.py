from datetime import date

import pytest

from financeiro.domain.recurrence import occurrence_date, occurs_in


@pytest.mark.parametrize(
    ("start", "end", "month", "expected"),
    [
        (date(2026, 3, 1), None, date(2026, 2, 1), False),
        (date(2026, 3, 1), None, date(2026, 3, 15), True),
        (date(2026, 3, 1), None, date(2030, 1, 1), True),
        (date(2026, 3, 1), date(2026, 12, 1), date(2026, 12, 1), True),
        (date(2026, 3, 1), date(2026, 12, 1), date(2027, 1, 1), False),
    ],
)
def test_occurs_in_respects_start_and_end(start, end, month, expected):
    assert occurs_in(start, end, month) is expected


def test_occurrence_date_clamps_to_month_end():
    assert occurrence_date(date(2026, 2, 1), 31) == date(2026, 2, 28)
    assert occurrence_date(date(2026, 10, 1), 25) == date(2026, 10, 25)

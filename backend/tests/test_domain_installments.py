from datetime import date

import pytest

from financeiro.domain.installments import installment_dates, split_amount


@pytest.mark.parametrize(
    ("total", "count", "expected"),
    [
        (100, 3, [34, 33, 33]),
        (120000, 10, [12000] * 10),
        (1000, 1, [1000]),
        (101, 2, [51, 50]),
        (5, 5, [1, 1, 1, 1, 1]),
    ],
)
def test_split_amount_keeps_every_cent(total, count, expected):
    assert split_amount(total, count) == expected


@pytest.mark.parametrize(("total", "count"), [(4, 5), (100, 0)])
def test_split_amount_rejects_impossible_splits(total, count):
    with pytest.raises(ValueError, match="parcelas"):
        split_amount(total, count)


@pytest.mark.parametrize(
    ("purchase", "count", "expected"),
    [
        (date(2026, 1, 31), 3, [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31)]),
        (date(2026, 11, 15), 3, [date(2026, 11, 15), date(2026, 12, 15), date(2027, 1, 15)]),
        (date(2024, 1, 30), 2, [date(2024, 1, 30), date(2024, 2, 29)]),
    ],
)
def test_installment_dates_keep_the_original_day(purchase, count, expected):
    assert installment_dates(purchase, count) == expected

import pytest

from financeiro.domain.budget import Entry, Plan, aggregate, budget_lines, planned_amount, thermometer
from financeiro.domain.enums import Bucket, Kind, Thermometer

PLAN_50_30_20 = Plan(needs_pct=50, wants_pct=30, savings_pct=20)


def test_aggregate_separates_realized_and_pending():
    totals = aggregate(
        [
            Entry(Kind.INCOME, None, 300_000, pending=False),
            Entry(Kind.INCOME, None, 50_000, pending=True),
            Entry(Kind.EXPENSE, Bucket.NEEDS, 100_000, pending=False),
            Entry(Kind.EXPENSE, Bucket.NEEDS, 20_000, pending=True),
            Entry(Kind.EXPENSE, Bucket.WANTS, 30_000, pending=False),
            Entry(Kind.EXPENSE, Bucket.SAVINGS, 60_000, pending=False),
        ]
    )
    assert (totals.income.realized, totals.income.pending, totals.income.total) == (300_000, 50_000, 350_000)
    assert totals.expenses[Bucket.NEEDS].total == 120_000
    assert totals.spending == 150_000
    assert totals.balance == 140_000
    assert totals.realized_balance == 110_000


@pytest.mark.parametrize(
    ("income", "percent", "expected"),
    [(210_000, 50, 105_000), (333_333, 30, 100_000), (1, 50, 1), (0, 50, 0)],
)
def test_planned_amount_rounds_to_nearest_cent(income, percent, expected):
    assert planned_amount(income, percent) == expected


def test_budget_lines_report_overspending_beyond_100_percent():
    totals = aggregate(
        [
            Entry(Kind.INCOME, None, 200_000, pending=False),
            Entry(Kind.EXPENSE, Bucket.NEEDS, 120_000, pending=False),
            Entry(Kind.EXPENSE, Bucket.WANTS, 30_000, pending=False),
            Entry(Kind.EXPENSE, Bucket.SAVINGS, 60_000, pending=False),
        ]
    )
    lines = {line.bucket: line for line in budget_lines(totals, PLAN_50_30_20)}
    assert (lines[Bucket.NEEDS].planned, lines[Bucket.NEEDS].remaining, lines[Bucket.NEEDS].used_pct) == (
        100_000,
        -20_000,
        120.0,
    )
    assert (lines[Bucket.WANTS].planned, lines[Bucket.WANTS].used_pct) == (60_000, 50.0)
    assert (lines[Bucket.SAVINGS].planned, lines[Bucket.SAVINGS].used_pct) == (40_000, 150.0)


def test_budget_lines_without_income_have_no_percentage():
    lines = budget_lines(aggregate([Entry(Kind.EXPENSE, Bucket.NEEDS, 5_000, pending=False)]), PLAN_50_30_20)
    assert [line.used_pct for line in lines] == [None, None, None]


@pytest.mark.parametrize(
    ("income", "spending", "expected"),
    [
        (0, 0, (Thermometer.NO_DATA, None)),
        (0, 1_000, (Thermometer.NEGATIVE, None)),
        (100_000, 80_000, (Thermometer.CONTROLLED, 80.0)),
        (100_000, 80_100, (Thermometer.WARNING, 80.1)),
        (100_000, 100_000, (Thermometer.WARNING, 100.0)),
        (100_000, 100_100, (Thermometer.NEGATIVE, 100.1)),
    ],
)
def test_thermometer_thresholds_follow_the_plan(income, spending, expected):
    assert thermometer(income, spending, PLAN_50_30_20) == expected


def test_saving_as_planned_keeps_thermometer_controlled():
    # Na planilha, poupança contava como gasto: seguir o plano 50/30/20 dava 100% e "Negativado".
    totals = aggregate(
        [
            Entry(Kind.INCOME, None, 100_000, pending=False),
            Entry(Kind.EXPENSE, Bucket.NEEDS, 50_000, pending=False),
            Entry(Kind.EXPENSE, Bucket.WANTS, 30_000, pending=False),
            Entry(Kind.EXPENSE, Bucket.SAVINGS, 20_000, pending=False),
        ]
    )
    assert thermometer(totals.income.total, totals.spending, PLAN_50_30_20)[0] is Thermometer.CONTROLLED

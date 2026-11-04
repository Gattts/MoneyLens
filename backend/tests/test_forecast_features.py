import math
from datetime import date

import pytest

from financeiro.domain.months import first_day
from financeiro.forecast.baseline import baseline_cents
from financeiro.forecast.features import (
    FEATURE_NAMES,
    MIN_SCALE_CENTS,
    SNAPSHOT_DAYS,
    categories_to_forecast,
    snapshot,
    training_snapshots,
)
from financeiro.forecast.history import Expense
from financeiro.forecast.scoring import score
from financeiro.forecast.synthetic import synthetic_history

FOOD, RENT = 1, 2
SEP, OCT, NOV = date(2026, 9, 1), date(2026, 10, 1), date(2026, 11, 1)


def _e(day: date, category: int, cents: int, fixed: bool = False) -> Expense:
    """Despesa fora do cartão: o mês de pagamento é o da data."""
    return Expense(day, first_day(day), category, cents, fixed)


HISTORY = [
    _e(date(2026, 8, 3), FOOD, 20_000),
    _e(date(2026, 8, 5), RENT, 150_000, fixed=True),
    _e(date(2026, 9, 2), FOOD, 10_000),
    _e(date(2026, 9, 20), FOOD, 30_000),
    _e(date(2026, 9, 5), RENT, 150_000, fixed=True),
    _e(date(2026, 10, 4), FOOD, 5_000),
    _e(date(2026, 10, 12), FOOD, 7_000),
    _e(date(2026, 10, 25), RENT, 150_000, fixed=True),
]


def _named(values) -> dict[str, float]:
    return dict(zip(FEATURE_NAMES, values, strict=True))


def test_snapshot_measures_for_a_day_of_a_closed_month():
    shot = snapshot(HISTORY, FOOD, OCT, 10)
    # média de agosto (200) e setembro (400) = 300 → escala R$ 300
    assert shot.scale_cents == 30_000
    values = _named(shot.values)
    assert values["spent_to_date"] == pytest.approx(5_000 / 30_000)
    assert values["scheduled_ahead"] == 0
    assert values["mean_last_months"] == pytest.approx(1.0)
    assert values["last_month"] == pytest.approx(40_000 / 30_000)
    assert values["month_fraction"] == pytest.approx(10 / 31)
    assert values["weekends_left"] == pytest.approx(6 / 10)  # sáb/dom de 11 a 31/10/2026
    assert values["months_of_history"] == pytest.approx(2 / 6)
    # o alvo é o que ainda entrou depois do dia 10 (R$ 70); os R$ 50 de antes já estavam comprometidos
    assert (shot.committed_cents, shot.target_cents) == (5_000, 7_000)


def test_fixed_bills_still_to_come_count_until_their_day():
    before = _named(snapshot(HISTORY, RENT, OCT, 20).values)
    after = _named(snapshot(HISTORY, RENT, OCT, 25).values)
    scale = snapshot(HISTORY, RENT, OCT, 20).scale_cents
    assert before["scheduled_ahead"] == pytest.approx(150_000 / scale)
    assert after["scheduled_ahead"] == 0


def test_current_month_uses_the_pending_fixed_bills_given():
    shot = snapshot(HISTORY, RENT, NOV, 3, ahead_cents=150_000)
    assert _named(shot.values)["scheduled_ahead"] == pytest.approx(150_000 / shot.scale_cents)
    assert shot.target_cents is None


def test_category_without_history_falls_back_to_the_minimum_scale():
    shot = snapshot([_e(date(2026, 10, 2), 9, 3_000)], 9, OCT, 5)
    assert shot.scale_cents == MIN_SCALE_CENTS
    assert all(math.isfinite(value) for value in shot.values)
    assert _named(shot.values)["mean_last_months"] == 0


@pytest.mark.parametrize(
    ("month", "day", "fraction", "weekends"),
    [
        (date(2027, 2, 1), 28, 1.0, 0),
        (date(2026, 10, 1), 31, 1.0, 0),
        (date(2027, 2, 1), 31, 1.0, 0),  # dia além do fim do mês vira o último dia
    ],
)
def test_month_edges(month, day, fraction, weekends):
    values = _named(snapshot(HISTORY, FOOD, month, day).values)
    assert values["month_fraction"] == pytest.approx(fraction)
    assert values["weekends_left"] == weekends


def test_history_is_capped_at_six_months():
    long = [_e(date(2026, month, 10), FOOD, 1_000) for month in range(1, 11)]
    assert _named(snapshot(long, FOOD, NOV, 5).values)["months_of_history"] == 1.0


def test_training_snapshots_use_only_closed_months():
    shots = training_snapshots(HISTORY, until_month=OCT)
    assert {shot.month for shot in shots} == {date(2026, 8, 1), SEP}
    per_month_category = {(shot.month, shot.category_id) for shot in shots}
    assert len(shots) == len(per_month_category) * len(SNAPSHOT_DAYS)
    assert all(shot.target_cents is not None for shot in shots)


def test_categories_to_forecast_include_recent_spending_and_pending_bills():
    assert categories_to_forecast(HISTORY, NOV, {7: 1_000}) == [FOOD, RENT, 7]
    assert categories_to_forecast(HISTORY, date(2027, 6, 1), {}) == []


def test_baseline_with_history_adds_pending_bills_and_daily_pace():
    # outubro, dia 10: gasto 50; variável de ago+set = 600 em 61 dias; faltam 21 dias
    assert baseline_cents(HISTORY, FOOD, OCT, date(2026, 10, 10), 0) == 5_000 + round(60_000 / 61 * 21)


def test_baseline_without_history_projects_the_month_pace():
    only = [_e(date(2026, 10, 2), 9, 3_000)]
    assert baseline_cents(only, 9, OCT, date(2026, 10, 10), 0) == round(3_000 / 10 * 31)


# Mês de pagamento: compra no cartão conta no mês em que a fatura vence (Expense.month).


def test_card_purchase_paid_in_the_month_counts_from_day_one():
    expenses = [
        Expense(date(2026, 10, 20), NOV, FOOD, 8_000, False),  # no cartão, paga em novembro
        Expense(date(2026, 11, 3), NOV, FOOD, 2_000, False),
    ]
    shot = snapshot(expenses, FOOD, NOV, 1)
    assert round(_named(shot.values)["spent_to_date"] * shot.scale_cents) == 8_000
    assert (shot.committed_cents, shot.target_cents) == (8_000, 2_000)  # o alvo é o que entrou depois


def test_installment_ahead_is_already_known():
    expenses = [
        Expense(date(2026, 11, 25), NOV, FOOD, 5_000, True),  # parcela já lançada
        Expense(date(2026, 11, 3), NOV, FOOD, 2_000, False),
    ]
    shot = snapshot(expenses, FOOD, NOV, 10)
    assert round(_named(shot.values)["scheduled_ahead"] * shot.scale_cents) == 5_000


def test_baseline_does_not_count_last_month_card_purchase_twice():
    history = [
        Expense(date(2026, 9, 10), SEP, FOOD, 3_000, False),
        Expense(date(2026, 10, 10), OCT, FOOD, 3_000, False),
        Expense(date(2026, 10, 20), NOV, FOOD, 8_000, False),  # cartão: já comprometido em novembro
    ]
    # comprometido + média diária das avulsas de setembro e outubro (6.000 / 61 dias) × 15 dias
    assert baseline_cents(history, FOOD, NOV, date(2026, 11, 15), 0) == 8_000 + round(6_000 / 61 * 15)


def test_synthetic_history_has_card_purchases_paid_later_and_scheduled_ones():
    expenses = synthetic_history(seed=1, months=6, categories=8)
    assert any(expense.month > first_day(expense.date) for expense in expenses)
    assert any(expense.scheduled for expense in expenses)


def test_score_compares_totals_and_never_puts_the_model_below_committed():
    # comprometido 5.000 e entraram mais 7.000; o modelo previu -1.000 de restante (vira 0) e teto de 8.000;
    # a estatística deu 12.000
    assert score(
        median_cents=-1_000,
        upper_cents=8_000,
        committed_cents=5_000,
        target_cents=7_000,
        baseline_cents=12_000,
    ) == (7_000, 0, True)


def test_closed_month_target_is_what_entered_after_the_day():
    expenses = [
        Expense(date(2026, 10, 20), NOV, FOOD, 8_000, False),  # cartão de outubro, paga em novembro
        Expense(date(2026, 11, 25), NOV, FOOD, 5_000, True),  # parcela já lançada
        Expense(date(2026, 11, 28), NOV, FOOD, 2_000, False),  # compra avulsa depois do dia 10
    ]
    shot = snapshot(expenses, FOOD, NOV, 10)
    assert (shot.committed_cents, shot.target_cents) == (13_000, 2_000)

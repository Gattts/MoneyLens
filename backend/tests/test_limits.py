from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from financeiro.domain.enums import LimitAlertKind
from financeiro.models import LimitAlert, SpendingLimit
from financeiro.services import limits
from financeiro.services.limits import (
    Suggestion,
    check_limits,
    insert_alert,
    limit_statuses,
    month_spent,
    reached_kinds,
    reset_months,
    suggest_limit,
)
from tests.factories import create_category, create_income_category, create_recurring, create_transaction

OCTOBER = date(2026, 10, 1)
DAY = date(2026, 10, 27)
R50, R90, R100 = LimitAlertKind.REACHED_50, LimitAlertKind.REACHED_90, LimitAlertKind.REACHED_100
FORECAST = LimitAlertKind.FORECAST


@pytest.fixture(autouse=True)
def no_forecast(monkeypatch):
    """A previsão real roda o modelo base: cada teste diz o provável que quer (lançar também confere)."""
    monkeypatch.setattr(limits, "forecast_p50", lambda *args: {})


def forecast(monkeypatch, values: dict[int, int]) -> None:
    monkeypatch.setattr(limits, "forecast_p50", lambda *args: values)


def spend(client, category_id: int, cents: int, day: str) -> None:
    create_transaction(client, category_id, amount_cents=cents, date=day)


def silent_by_kind(db, limit: SpendingLimit) -> dict[LimitAlertKind, bool]:
    db.expire_all()
    return {
        alert.kind: alert.silent
        for alert in db.scalars(select(LimitAlert).where(LimitAlert.limit_id == limit.id))
    }


def make_limit(db, user, category_id: int, amount_cents: int) -> SpendingLimit:
    limit = SpendingLimit(user_id=user.id, category_id=category_id, amount_cents=amount_cents)
    db.add(limit)
    db.commit()
    return limit


def make_percent_limit(db, user, category_id: int, percent: int) -> SpendingLimit:
    limit = SpendingLimit(user_id=user.id, category_id=category_id, income_percent=percent)
    db.add(limit)
    db.commit()
    return limit


def make_alert(user, limit: SpendingLimit, **overrides) -> LimitAlert:
    values = {
        "user_id": user.id,
        "limit_id": limit.id,
        "month": OCTOBER,
        "kind": LimitAlertKind.REACHED_50,
        "spent_cents": 15_000,
        "limit_cents": limit.amount_cents,
    }
    return LimitAlert(**(values | overrides))


def test_alert_is_unique_per_limit_month_and_kind(client, db, user):
    limit = make_limit(db, user, create_category(client)["id"], 30_000)
    db.add(make_alert(user, limit))
    db.commit()
    db.add(make_alert(user, limit))
    with pytest.raises(IntegrityError):
        db.commit()


def test_limit_amount_must_be_positive(client, db, user):
    with pytest.raises(IntegrityError):
        make_limit(db, user, create_category(client)["id"], 0)


def test_one_limit_per_category(client, db, user):
    category_id = create_category(client)["id"]
    make_limit(db, user, category_id, 30_000)
    with pytest.raises(IntegrityError):
        make_limit(db, user, category_id, 40_000)


def test_deleting_the_category_deletes_its_limit_and_alerts(client, db, user):
    category = create_category(client)
    limit = make_limit(db, user, category["id"], 30_000)
    db.add(make_alert(user, limit))
    db.commit()
    assert client.delete(f"/api/categories/{category['id']}").status_code == 204
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(SpendingLimit)) == 0
    assert db.scalar(select(func.count()).select_from(LimitAlert)) == 0


def test_reached_kinds_by_percent():
    assert reached_kinds(14_999, 30_000, None, DAY) == set()
    assert reached_kinds(15_000, 30_000, None, DAY) == {R50}
    assert reached_kinds(27_000, 30_000, None, DAY) == {R50, R90}
    assert reached_kinds(30_000, 30_000, None, DAY) == {R50, R90, R100}


def test_forecast_from_day_7_and_only_below_the_limit():
    assert FORECAST not in reached_kinds(10_000, 30_000, 31_000, date(2026, 10, 6))
    assert FORECAST in reached_kinds(10_000, 30_000, 30_000, date(2026, 10, 7))
    assert FORECAST not in reached_kinds(30_000, 30_000, 40_000, DAY)
    assert FORECAST not in reached_kinds(10_000, 30_000, None, DAY)


def test_check_creates_one_visible_alert_and_silences_the_rest(client, db, user):
    category = create_category(client)["id"]
    limit = make_limit(db, user, category, 30_000)
    spend(client, category, 28_500, "2026-10-20")
    check_limits(db, user.id, DAY)
    db.commit()
    assert silent_by_kind(db, limit) == {R90: False, R50: True}
    visible = db.scalar(select(LimitAlert).where(LimitAlert.kind == R90))
    assert (visible.spent_cents, visible.limit_cents, visible.month) == (28_500, 30_000, OCTOBER)
    assert (visible.read_at, visible.forecast_cents) == (None, None)


def test_severity_order(client, db, user, monkeypatch):
    # Os tetos vêm depois dos gastos: cada lançamento já confere todos os tetos, e aqui interessa uma
    # conferência só.
    over = create_category(client, name="Lazer")["id"]
    near = create_category(client, name="Delivery")["id"]
    spend(client, over, 30_000, "2026-10-20")
    spend(client, near, 27_000, "2026-10-20")
    over_limit = make_limit(db, user, over, 30_000)
    near_limit = make_limit(db, user, near, 30_000)
    forecast(monkeypatch, {over: 40_000, near: 35_000})
    check_limits(db, user.id, DAY)
    db.commit()
    assert silent_by_kind(db, over_limit) == {R100: False, R90: True, R50: True}
    assert silent_by_kind(db, near_limit) == {FORECAST: False, R90: True, R50: True}
    warning = db.scalar(select(LimitAlert).where(LimitAlert.kind == FORECAST))
    assert warning.forecast_cents == 35_000


def test_same_mark_is_not_repeated_and_returns_next_month(client, db, user):
    category = create_category(client)["id"]
    limit = make_limit(db, user, category, 30_000)
    spend(client, category, 15_000, "2026-10-10")
    check_limits(db, user.id, DAY)
    check_limits(db, user.id, DAY)
    db.commit()
    assert db.scalar(select(func.count()).select_from(LimitAlert)) == 1
    spend(client, category, 15_000, "2026-11-02")
    check_limits(db, user.id, date(2026, 11, 2))
    db.commit()
    db.expire_all()
    months = [alert.month for alert in db.scalars(select(LimitAlert).where(LimitAlert.limit_id == limit.id))]
    assert sorted(months) == [OCTOBER, date(2026, 11, 1)]


def test_spent_counts_from_day_one_to_today(client, db, user):
    category = create_category(client)["id"]
    make_limit(db, user, category, 30_000)
    spend(client, category, 15_000, "2026-09-30")
    spend(client, category, 15_000, "2026-10-28")
    assert month_spent(db, user.id, OCTOBER, DAY).get(category, 0) == 0
    check_limits(db, user.id, DAY)
    db.commit()
    assert db.scalar(select(func.count()).select_from(LimitAlert)) == 0
    check_limits(db, user.id, date(2026, 10, 28))
    db.commit()
    assert db.scalar(select(LimitAlert.kind)) == R50


def test_inactive_limit_makes_no_alert(client, db, user):
    category = create_category(client)
    spend(client, category["id"], 30_000, "2026-10-20")  # antes de arquivar: arquivada não aceita lançamento
    make_limit(db, user, category["id"], 30_000)
    body = {key: category[key] for key in ("name", "icon", "kind", "default_bucket")} | {"archived": True}
    assert client.put(f"/api/categories/{category['id']}", json=body).status_code == 200
    check_limits(db, user.id, DAY)
    db.commit()
    assert db.scalar(select(func.count()).select_from(LimitAlert)) == 0
    assert [status.active for status in limit_statuses(db, user.id, DAY, with_forecast=True)] == [False]


def test_no_limits_means_no_forecast(client, db, user, monkeypatch):
    def fail(*args):
        raise AssertionError("a previsão não devia rodar")

    monkeypatch.setattr(limits, "forecast_p50", fail)
    check_limits(db, user.id, DAY)
    assert limit_statuses(db, user.id, DAY, with_forecast=True) == []


def test_forecast_failure_still_records_percent_alerts(client, db, user, monkeypatch):
    def broken(*args):
        raise RuntimeError("modelo indisponível")

    category = create_category(client)["id"]
    limit = make_limit(db, user, category, 30_000)
    spend(client, category, 15_000, "2026-10-20")
    monkeypatch.setattr(limits, "forecast_p50", broken)
    check_limits(db, user.id, DAY)
    db.commit()
    assert silent_by_kind(db, limit) == {R50: False}


def test_inserting_an_existing_alert_is_ignored(client, db, user):
    limit = make_limit(db, user, create_category(client)["id"], 30_000)
    values = {
        "user_id": user.id,
        "limit_id": limit.id,
        "month": OCTOBER,
        "kind": R50,
        "spent_cents": 15_000,
        "limit_cents": 30_000,
        "forecast_cents": None,
        "silent": False,
    }
    assert insert_alert(db, values) is True
    assert insert_alert(db, values) is False
    db.commit()
    assert db.scalar(select(func.count()).select_from(LimitAlert)) == 1


def test_limit_statuses_fields_and_order(client, db, user, monkeypatch):
    low = create_category(client, name="Mercado")["id"]
    high = create_category(client, name="Lazer")["id"]
    archived = create_category(client, name="Antiga", archived=True)["id"]
    make_limit(db, user, low, 30_000)
    make_limit(db, user, high, 10_000)
    make_limit(db, user, archived, 10_000)
    forecast(monkeypatch, {low: 31_000})
    spend(client, low, 10_001, "2026-10-20")
    spend(client, high, 6_000, "2026-10-20")
    statuses = limit_statuses(db, user.id, DAY, with_forecast=True)
    assert [(s.category.name, s.percent, s.active) for s in statuses] == [
        ("Lazer", 60, True),
        ("Mercado", 33, True),
        ("Antiga", 0, False),
    ]
    mercado = statuses[1]
    assert (mercado.spent_cents, mercado.p50_cents, mercado.will_exceed) == (10_001, 31_000, True)
    assert statuses[0].p50_cents is None
    assert limit_statuses(db, user.id, DAY, with_forecast=False)[1].p50_cents is None


def test_reset_months_deletes_this_and_the_next_months_of_this_limit(client, db, user):
    first = make_limit(db, user, create_category(client, name="Lazer")["id"], 30_000)
    second = make_limit(db, user, create_category(client, name="Mercado")["id"], 30_000)
    db.add_all(
        [
            make_alert(user, first),
            make_alert(user, first, month=date(2026, 9, 1)),
            make_alert(user, first, month=date(2026, 11, 1)),  # compra no cartão paga em novembro
            make_alert(user, second),
        ]
    )
    db.commit()
    reset_months(db, first, DAY)
    db.commit()
    rest = {(alert.limit_id, alert.month) for alert in db.scalars(select(LimitAlert))}
    assert rest == {(first.id, date(2026, 9, 1)), (second.id, OCTOBER)}


def spend_history(client, category_id: int, history: dict[str, int]) -> None:
    for day, cents in history.items():
        spend(client, category_id, cents, day)


def test_suggestion_uses_forecast_rounded_up(client, db, user, monkeypatch):
    category = create_category(client)["id"]
    spend_history(client, category, {"2026-07-10": 25_000, "2026-08-10": 31_000, "2026-09-10": 28_000})
    forecast(monkeypatch, {category: 30_412})
    assert suggest_limit(db, user.id, category, DAY) == Suggestion(31_000, 25_000, 31_000, 3)


def test_suggestion_falls_back_to_the_average(client, db, user):
    category = create_category(client)["id"]
    spend_history(client, category, {"2026-07-10": 25_000, "2026-08-10": 31_000, "2026-09-10": 28_500})
    assert suggest_limit(db, user.id, category, DAY) == Suggestion(29_000, 25_000, 31_000, 3)


def test_suggestion_uses_the_last_three_months_with_any_expense(client, db, user):
    category = create_category(client, name="Lazer")["id"]
    other = create_category(client, name="Mercado")["id"]
    spend_history(client, category, {"2026-06-10": 40_000, "2026-08-10": 31_000, "2026-09-10": 28_000})
    spend(client, other, 5_000, "2026-07-10")  # julho conta como mês, com 0 em Lazer
    assert suggest_limit(db, user.id, category, DAY) == Suggestion(20_000, 0, 31_000, 3)


def test_no_history_means_no_suggestion(client, db, user, monkeypatch):
    category = create_category(client)["id"]
    spend(client, category, 10_000, "2026-10-05")
    forecast(monkeypatch, {category: 12_000})
    assert suggest_limit(db, user.id, category, DAY) == Suggestion(None, 0, 0, 0)


def test_no_forecast_alert_after_passing_the_limit(client, db, user, monkeypatch):
    category = create_category(client)["id"]
    first = create_transaction(client, category, amount_cents=30_000, date="2026-10-10")
    limit = make_limit(db, user, category, 30_000)
    check_limits(db, user.id, DAY)
    db.commit()
    assert client.delete(f"/api/transactions/{first['id']}").status_code == 204
    spend(client, category, 20_000, "2026-10-20")
    forecast(monkeypatch, {category: 35_000})
    check_limits(db, user.id, DAY)
    db.commit()
    assert FORECAST not in silent_by_kind(db, limit)


@pytest.mark.parametrize(
    "fields",
    [{"amount_cents": 30_000, "income_percent": 10}, {}, {"income_percent": 0}, {"income_percent": 101}],
    ids=["os dois", "nenhum", "0%", "101%"],
)
def test_limit_has_either_an_amount_or_an_income_percent(client, db, user, fields):
    db.add(SpendingLimit(user_id=user.id, category_id=create_category(client)["id"], **fields))
    with pytest.raises(IntegrityError):
        db.commit()


def income(client, cents: int) -> int:
    salary = create_income_category(client)["id"]
    create_transaction(
        client, salary, kind="income", amount_cents=cents, date="2026-10-05", payment_method="transfer"
    )
    return salary


def test_percent_limit_uses_the_planned_income_of_the_month(client, db, user):
    salary = income(client, 200_000)
    create_recurring(  # renda fixa ainda não confirmada: entra na renda prevista, como no Orçamento
        client, salary, kind="income", amount_cents=100_000, day_of_month=28, payment_method="transfer"
    )
    category = create_category(client)["id"]
    spend(client, category, 15_000, "2026-10-20")
    make_percent_limit(db, user, category, 10)
    [status] = limit_statuses(db, user.id, DAY, with_forecast=False)
    assert (status.amount_cents, status.income_cents, status.income_percent) == (30_000, 300_000, 10)
    assert (status.percent, status.active, status.no_income) == (50, True, False)
    check_limits(db, user.id, DAY)
    db.commit()
    alert = db.scalar(select(LimitAlert))
    assert (alert.kind, alert.limit_cents) == (R50, 30_000)


def test_percent_limit_without_income_is_inactive(client, db, user):
    category = create_category(client)["id"]
    spend(client, category, 15_000, "2026-10-20")
    make_percent_limit(db, user, category, 10)
    [status] = limit_statuses(db, user.id, DAY, with_forecast=False)
    assert (status.active, status.no_income, status.amount_cents, status.percent) == (False, True, 0, 0)
    check_limits(db, user.id, DAY)
    db.commit()
    assert db.scalar(select(func.count()).select_from(LimitAlert)) == 0


def test_suggestion_also_gives_the_percent_of_income(client, db, user, monkeypatch):
    income(client, 300_000)
    category = create_category(client)["id"]
    spend_history(client, category, {"2026-07-10": 25_000, "2026-08-10": 31_000, "2026-09-10": 28_000})
    forecast(monkeypatch, {category: 30_412})
    suggestion = suggest_limit(db, user.id, category, DAY)
    assert (suggestion.suggested_cents, suggestion.income_cents, suggestion.suggested_percent) == (
        31_000,
        300_000,
        11,
    )

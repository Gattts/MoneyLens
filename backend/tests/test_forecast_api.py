from datetime import date

import numpy as np
import pytest

from financeiro.forecast import BASE_ONNX, predict
from financeiro.forecast.features import FEATURE_VERSION
from financeiro.forecast.store import save_model
from tests.factories import create_category, create_transaction

METRICS = {"mae_model_cents": 1000, "mae_baseline_cents": 2000, "coverage_p90": 0.8, "months": 3}


@pytest.fixture(autouse=True)
def _clean_cache():
    predict.clear_cache()
    yield
    predict.clear_cache()


@pytest.fixture
def food(client):
    """Hoje (testes) é 27/10/2026. Histórico de agosto e setembro e R$ 100 gastos em outubro."""
    category = create_category(client, name="Comida fora", default_bucket="wants")
    for day in ("2026-08-10", "2026-09-10", "2026-10-05"):
        create_transaction(client, category["id"], amount_cents=10_000, date=day)
    return category


def _line(body: dict, category_id: int) -> dict:
    return next(item for item in body["categories"] if item["category_id"] == category_id)


def _fixed_prediction(monkeypatch, median: float, upper: float):
    """Saída fixa do modelo (em escala): os alertas não dependem dos números do modelo real."""
    monkeypatch.setattr(
        predict, "run_model", lambda _session, features: np.array([[median, upper]] * len(features))
    )


def test_forecast_with_the_base_model(client, food):
    response = client.get("/api/forecast")
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["month"], body["day"], body["source"]) == ("2026-10", 27, "base_model")
    line = _line(body, food["id"])
    assert (line["name"], line["spent_cents"]) == ("Comida fora", 10_000)
    assert line["p90_cents"] >= line["p50_cents"] >= line["spent_cents"]
    assert line["baseline_cents"] > 0
    assert body["total"]["spent_cents"] == 10_000


def test_own_model_is_used_when_saved(client, db, user, food):
    save_model(db, user.id, BASE_ONNX.read_bytes(), METRICS, trained_until=date(2026, 9, 1))
    assert client.get("/api/forecast").json()["source"] == "model"


def test_model_of_an_old_feature_version_is_ignored(client, db, user, food):
    stale = save_model(db, user.id, BASE_ONNX.read_bytes(), METRICS, trained_until=date(2026, 9, 1))
    stale.feature_version = FEATURE_VERSION - 1
    db.commit()
    assert client.get("/api/forecast").json()["source"] == "base_model"


def test_alert_when_spending_is_already_above_the_ceiling(client, monkeypatch, food):
    _fixed_prediction(monkeypatch, 0.3, 0.5)  # escala R$ 100 → provável R$ 30, teto R$ 50; gasto R$ 100
    line = _line(client.get("/api/forecast").json(), food["id"])
    assert (line["alert"], line["alert_reason"]) == (True, "above")
    assert line["p50_cents"] == 10_000  # nunca abaixo do que já foi gasto


def test_alert_when_the_month_pace_goes_above_the_ceiling(client, monkeypatch, food):
    _fixed_prediction(monkeypatch, 1.0, 1.1)  # teto R$ 110; ritmo: R$ 100 em 27 dias → R$ 114,81 no mês
    line = _line(client.get("/api/forecast").json(), food["id"])
    assert (line["alert"], line["alert_reason"]) == (True, "pace")


def test_no_alert_inside_the_range(client, monkeypatch, food):
    _fixed_prediction(monkeypatch, 1.5, 2.0)
    line = _line(client.get("/api/forecast").json(), food["id"])
    assert (line["alert"], line["alert_reason"]) == (False, None)


def test_no_alert_before_day_seven_or_below_fifty_reais(client, app, monkeypatch, food):
    from financeiro.deps import get_today  # noqa: PLC0415

    _fixed_prediction(monkeypatch, 0.1, 0.2)
    app.dependency_overrides[get_today] = lambda: date(2026, 10, 6)
    assert _line(client.get("/api/forecast").json(), food["id"])["alert"] is False
    app.dependency_overrides[get_today] = lambda: date(2026, 10, 27)
    small = create_category(client, name="Banca", default_bucket="wants")
    create_transaction(client, small["id"], amount_cents=4_000, date="2026-10-20")
    assert _line(client.get("/api/forecast").json(), small["id"])["alert"] is False


def test_each_user_gets_only_their_own_model(client, other_client, db, user, second_user):
    """O modelo do outro usuário está quebrado: se fosse usado aqui, a previsão falharia."""
    save_model(db, user.id, BASE_ONNX.read_bytes(), METRICS, trained_until=date(2026, 9, 1))
    save_model(db, second_user.id, b"nao e um modelo onnx", METRICS, trained_until=date(2026, 9, 1))
    assert client.get("/api/forecast").json()["source"] == "model"
    theirs = other_client.get("/api/forecast")
    assert theirs.status_code == 200
    assert theirs.json()["source"] == "base_model"  # modelo ilegível: volta para o base


def test_models_history_lists_only_my_versions(client, other_client, db, user):
    save_model(db, user.id, BASE_ONNX.read_bytes(), METRICS, trained_until=date(2026, 9, 1))
    save_model(db, user.id, BASE_ONNX.read_bytes(), METRICS, trained_until=date(2026, 9, 1))
    models = client.get("/api/forecast/models").json()
    assert [(item["version"], item["active"], item["trained_until"]) for item in models] == [
        (2, True, "2026-09"),
        (1, False, "2026-09"),
    ]
    assert models[0]["metrics"]["mae_model_cents"] == 1000
    assert "onnx" not in models[0]
    assert other_client.get("/api/forecast/models").json() == []


def test_reused_user_id_never_gets_the_previous_users_model(db):
    """No SQLite, excluir o usuário de maior id e criar outro reaproveita o id: o cache não pode misturar."""
    from financeiro.models import User  # noqa: PLC0415

    first = User(username="ana", username_key="ana", password_hash="x", is_admin=False)
    db.add(first)
    db.commit()
    save_model(db, first.id, BASE_ONNX.read_bytes(), METRICS, trained_until=date(2026, 9, 1))
    assert predict.forecast_month(db, first.id, date(2026, 10, 27)).source == "model"  # enche o cache
    reused_id = first.id
    db.delete(first)
    db.commit()
    second = User(username="bia", username_key="bia", password_hash="x", is_admin=False)
    db.add(second)
    db.commit()
    if second.id != reused_id:
        pytest.skip("este banco não reaproveita ids")
    save_model(db, second.id, b"modelo quebrado de outra pessoa", METRICS, trained_until=date(2026, 9, 1))
    assert predict.forecast_month(db, second.id, date(2026, 10, 27)).source == "base_model"


def test_forecast_says_how_many_closed_months_there_are(client, food):
    # agosto e setembro estão fechados; outubro é o mês atual e não conta
    assert client.get("/api/forecast").json()["history_months"] == 2


def test_forecast_without_history_has_zero_closed_months(client):
    assert client.get("/api/forecast").json()["history_months"] == 0

import json
from datetime import date

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from financeiro.cli import run_migrations, train_command
from financeiro.config import Settings
from financeiro.domain.enums import Bucket, Kind, PaymentMethod
from financeiro.forecast.features import FEATURE_VERSION
from financeiro.forecast.store import latest_model, list_models, save_model
from financeiro.models import Category, ForecastModel, Transaction, User

METRICS = {"mae_model_cents": 100, "mae_baseline_cents": 200, "coverage_p90": 0.9}


def test_versions_grow_per_user(db, user, second_user):
    first = save_model(db, user.id, b"a", METRICS, trained_until=date(2026, 9, 1))
    second = save_model(db, user.id, b"b", METRICS, trained_until=date(2026, 9, 1))
    other = save_model(db, second_user.id, b"c", METRICS, trained_until=date(2026, 9, 1))
    assert (first.version, second.version, other.version) == (1, 2, 1)
    assert latest_model(db, user.id).onnx == b"b"
    assert [model.version for model in list_models(db, user.id)] == [2, 1]
    assert json.loads(second.metrics) == METRICS


def test_latest_model_ignores_an_old_feature_version(db, user):
    stale = save_model(db, user.id, b"old", METRICS, trained_until=date(2026, 9, 1))
    stale.feature_version = FEATURE_VERSION - 1
    db.commit()
    assert latest_model(db, user.id) is None


def _seed(session: Session, username: str, months: list[int]) -> None:
    user = User(username=username, username_key=username, password_hash="x", is_admin=False)
    session.add(user)
    session.flush()
    category = Category(user_id=user.id, name="Mercado", kind=Kind.EXPENSE, default_bucket=Bucket.NEEDS)
    session.add(category)
    session.flush()
    for month in months:
        for day, cents in ((3, 12_345), (12, 6_789), (21, 9_876)):
            session.add(
                Transaction(
                    user_id=user.id,
                    description="COMPRA SECRETA",
                    kind=Kind.EXPENSE,
                    amount_cents=cents,
                    date=date(2026, month, day),
                    category_id=category.id,
                    bucket=Bucket.NEEDS,
                    payment_method=PaymentMethod.PIX,
                )
            )
    session.commit()


def test_train_command_saves_a_model_per_user_and_prints_only_metrics(tmp_path, capsys):
    pytest.importorskip("torch")
    settings = Settings(_env_file=None, data_dir=tmp_path, secret_key="x" * 40)
    run_migrations(settings)
    engine = create_engine(settings.resolved_database_url)
    with Session(engine) as session:
        _seed(session, "ana", [7, 8, 9])
        _seed(session, "bia", [9])
    assert train_command(settings, None, today=date(2026, 10, 29)) == 0
    out = capsys.readouterr().out
    with Session(engine) as session:
        owners = session.scalars(
            select(User.username).join(ForecastModel, ForecastModel.user_id == User.id)
        ).all()
    assert owners == ["ana"]
    assert "bia: só 1 mês(es) fechado(s); continua com o modelo base." in out
    assert "ana:" in out and "versão 1" in out
    assert "COMPRA SECRETA" not in out and "123,45" not in out

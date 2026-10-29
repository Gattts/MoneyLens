from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from financeiro.domain.enums import LimitAlertKind
from financeiro.models import LimitAlert, SpendingLimit
from tests.factories import create_category

OCTOBER = date(2026, 10, 1)


def make_limit(db, user, category_id: int, amount_cents: int) -> SpendingLimit:
    limit = SpendingLimit(user_id=user.id, category_id=category_id, amount_cents=amount_cents)
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

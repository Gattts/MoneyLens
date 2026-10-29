import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from financeiro.domain.defaults import DEFAULT_RULES
from financeiro.domain.enums import Kind
from financeiro.domain.usernames import username_key
from financeiro.models import BudgetSettings, Category, CategoryRule
from financeiro.services.users import seed_defaults


def test_username_key_ignores_case_accents_and_outer_spaces():
    assert username_key("  João.Silva ") == "joao.silva"
    assert username_key("MÁRIA") == username_key("maria")


def test_seed_defaults_creates_the_package(db, user):
    seed_defaults(db, user.id)
    db.commit()
    categories = db.scalars(select(Category).where(Category.user_id == user.id)).all()
    assert len(categories) == 24
    assert {category.kind for category in categories} == {Kind.EXPENSE, Kind.INCOME}
    rules = db.scalar(select(func.count()).select_from(CategoryRule).where(CategoryRule.user_id == user.id))
    assert rules == len(DEFAULT_RULES)
    budget = db.scalar(select(BudgetSettings).where(BudgetSettings.user_id == user.id))
    assert (budget.needs_pct, budget.wants_pct, budget.savings_pct) == (50, 30, 20)


def test_category_names_are_unique_per_user(db, user, second_user):
    db.add_all(
        [
            Category(user_id=user.id, name="Pets", kind=Kind.EXPENSE, default_bucket="wants"),
            Category(user_id=second_user.id, name="Pets", kind=Kind.EXPENSE, default_bucket="wants"),
        ]
    )
    db.commit()
    db.add(Category(user_id=user.id, name="Pets", kind=Kind.EXPENSE, default_bucket="wants"))
    with pytest.raises(IntegrityError):
        db.commit()

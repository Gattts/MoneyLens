"""Usuários: pacote padrão de cada conta nova."""

from sqlalchemy.orm import Session

from financeiro.domain.defaults import DEFAULT_BUDGET, DEFAULT_CATEGORIES, DEFAULT_RULES
from financeiro.domain.enums import Bucket, Kind, MatchType, RuleSource
from financeiro.models import BudgetSettings, Category, CategoryRule


def seed_defaults(session: Session, user_id: int) -> None:
    """Cria as categorias, as palavras-chave das faturas e o orçamento 50/30/20 do usuário (sem commit)."""
    categories = [
        Category(
            user_id=user_id,
            icon=icon,
            name=name,
            kind=Kind(kind),
            default_bucket=Bucket(bucket) if bucket else None,
            description=description,
        )
        for icon, name, kind, bucket, description in DEFAULT_CATEGORIES
    ]
    session.add_all(categories)
    session.flush()
    ids = {category.name: category.id for category in categories}
    session.add_all(
        CategoryRule(
            user_id=user_id,
            pattern=pattern,
            match_type=MatchType.CONTAINS,
            category_id=ids[name],
            source=RuleSource.DEFAULT,
        )
        for pattern, name in DEFAULT_RULES
        if name in ids
    )
    needs, wants, savings = DEFAULT_BUDGET
    session.add(BudgetSettings(user_id=user_id, needs_pct=needs, wants_pct=wants, savings_pct=savings))

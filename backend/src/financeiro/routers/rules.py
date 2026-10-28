from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import Session

from financeiro.db import DbSession
from financeiro.domain.enums import Kind, RuleSource
from financeiro.domain.merchants import merchant_key
from financeiro.errors import conflict, invalid
from financeiro.models import CategoryRule
from financeiro.schemas.common import ItemId
from financeiro.schemas.rules import RuleIn, RuleOut
from financeiro.security import CurrentUser
from financeiro.services.entries import resolve_bucket
from financeiro.services.ownership import get_owned_or_404, owned

router = APIRouter(prefix="/category-rules", tags=["regras"])

NOT_FOUND = "Regra não encontrada."
MIN_PATTERN_LENGTH = 2


@router.get("")
def list_rules(session: DbSession, user: CurrentUser) -> list[RuleOut]:
    rules = session.scalars(
        owned(CategoryRule, user.id).order_by(CategoryRule.match_type, CategoryRule.pattern)
    ).all()
    return [RuleOut.model_validate(rule) for rule in rules]


@router.post("", status_code=201)
def create_rule(body: RuleIn, session: DbSession, user: CurrentUser) -> RuleOut:
    pattern = _validate(body, session, user.id)
    rule = CategoryRule(
        pattern=pattern,
        match_type=body.match_type,
        category_id=body.category_id,
        source=RuleSource.LEARNED,
        user_id=user.id,
    )
    session.add(rule)
    session.commit()
    return RuleOut.model_validate(rule)


@router.put("/{item_id}")
def update_rule(item_id: ItemId, body: RuleIn, session: DbSession, user: CurrentUser) -> RuleOut:
    rule = get_owned_or_404(session, CategoryRule, item_id, user.id, NOT_FOUND)
    rule.pattern = _validate(body, session, user.id, current=rule)
    rule.match_type = body.match_type
    rule.category_id = body.category_id
    session.commit()
    return RuleOut.model_validate(rule)


@router.delete("/{item_id}", status_code=204)
def delete_rule(item_id: ItemId, session: DbSession, user: CurrentUser) -> None:
    session.delete(get_owned_or_404(session, CategoryRule, item_id, user.id, NOT_FOUND))
    session.commit()


def _validate(body: RuleIn, session: Session, user_id: int, current: CategoryRule | None = None) -> str:
    """Confere a categoria e a repetição; devolve o padrão normalizado como os nomes das faturas."""
    pattern = merchant_key(body.pattern)
    if len(pattern.replace("*", "").replace(".", "").replace(" ", "")) < MIN_PATTERN_LENGTH:
        raise invalid("pattern", "Use pelo menos 2 letras ou números.")
    resolve_bucket(
        session,
        user_id=user_id,
        kind=Kind.EXPENSE,
        category_id=body.category_id,
        bucket=None,
        current_category_id=current.category_id if current else None,
    )
    same = select(CategoryRule.id).where(
        CategoryRule.user_id == user_id,
        CategoryRule.match_type == body.match_type,
        CategoryRule.pattern == pattern,
    )
    if current is not None:
        same = same.where(CategoryRule.id != current.id)
    if session.scalar(same) is not None:
        raise conflict("Já existe uma regra igual.")
    return pattern

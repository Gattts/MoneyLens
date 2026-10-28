from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import Session

from financeiro.db import DbSession
from financeiro.domain.enums import Kind
from financeiro.errors import conflict, invalid
from financeiro.models import Category, RecurringRule, Transaction
from financeiro.schemas.categories import CategoryIn, CategoryOut
from financeiro.schemas.common import ItemId
from financeiro.services.lookup import count_references, ensure_unique_name, get_or_404, name_key

router = APIRouter(prefix="/categories", tags=["categorias"])

NOT_FOUND = "Categoria não encontrada."


@router.get("")
def list_categories(session: DbSession) -> list[CategoryOut]:
    categories = session.scalars(select(Category)).all()
    ordered = sorted(categories, key=lambda c: (c.archived, c.kind, name_key(c.name)))
    return [CategoryOut.model_validate(category) for category in ordered]


@router.post("", status_code=201)
def create_category(body: CategoryIn, session: DbSession) -> CategoryOut:
    _validate(body, session)
    category = Category(**body.model_dump())
    session.add(category)
    session.commit()
    return CategoryOut.model_validate(category)


@router.put("/{item_id}")
def update_category(item_id: ItemId, body: CategoryIn, session: DbSession) -> CategoryOut:
    category = get_or_404(session, Category, item_id, NOT_FOUND)
    _validate(body, session, exclude_id=item_id)
    if body.kind != category.kind and _usage_count(session, item_id) > 0:
        raise conflict("Não é possível mudar o tipo de uma categoria que já tem lançamentos ou fixas.")
    for field, value in body.model_dump().items():
        setattr(category, field, value)
    session.commit()
    return CategoryOut.model_validate(category)


@router.delete("/{item_id}", status_code=204)
def delete_category(item_id: ItemId, session: DbSession) -> None:
    category = get_or_404(session, Category, item_id, NOT_FOUND)
    usage = _usage_count(session, item_id)
    if usage:
        raise conflict(
            f"Esta categoria é usada em {usage} lançamento(s) ou fixa(s). "
            "Arquive-a para escondê-la sem perder o histórico."
        )
    session.delete(category)
    session.commit()


def _validate(body: CategoryIn, session: Session, exclude_id: int | None = None) -> None:
    if body.kind is Kind.EXPENSE and body.default_bucket is None:
        raise invalid("default_bucket", "Escolha o grupo do orçamento: necessidade, desejo ou poupança.")
    if body.kind is Kind.INCOME and body.default_bucket is not None:
        raise invalid("default_bucket", "Categorias de receita não entram nos grupos do orçamento.")
    ensure_unique_name(session, Category, body.name, "Já existe uma categoria com esse nome.", exclude_id)


def _usage_count(session: Session, category_id: int) -> int:
    return count_references(
        session, Transaction.category_id == category_id, RecurringRule.category_id == category_id
    )

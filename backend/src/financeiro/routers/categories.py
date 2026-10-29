from fastapi import APIRouter
from sqlalchemy.orm import Session

from financeiro.db import DbSession
from financeiro.domain.enums import Kind
from financeiro.errors import conflict, invalid
from financeiro.models import Category, InvoiceLine, RecurringRule, Transaction
from financeiro.schemas.categories import CategoryIn, CategoryOut
from financeiro.schemas.common import ItemId
from financeiro.security import CurrentUser
from financeiro.services.lookup import count_references, ensure_unique_name, name_key
from financeiro.services.ownership import get_owned_or_404, owned

router = APIRouter(prefix="/categories", tags=["categorias"])

NOT_FOUND = "Categoria não encontrada."


@router.get("")
def list_categories(session: DbSession, user: CurrentUser) -> list[CategoryOut]:
    categories = session.scalars(owned(Category, user.id)).all()
    ordered = sorted(categories, key=lambda c: (c.archived, c.kind, name_key(c.name)))
    return [CategoryOut.model_validate(category) for category in ordered]


@router.post("", status_code=201)
def create_category(body: CategoryIn, session: DbSession, user: CurrentUser) -> CategoryOut:
    _validate(body, session, user.id)
    category = Category(**body.model_dump(), user_id=user.id)
    session.add(category)
    session.commit()
    return CategoryOut.model_validate(category)


@router.put("/{item_id}")
def update_category(item_id: ItemId, body: CategoryIn, session: DbSession, user: CurrentUser) -> CategoryOut:
    category = get_owned_or_404(session, Category, item_id, user.id, NOT_FOUND)
    _validate(body, session, user.id, exclude_id=item_id)
    if body.kind != category.kind and _usage_count(session, item_id) > 0:
        raise conflict("Não é possível mudar o tipo de uma categoria que já tem lançamentos ou fixas.")
    for field, value in body.model_dump().items():
        setattr(category, field, value)
    session.commit()
    return CategoryOut.model_validate(category)


@router.delete("/{item_id}", status_code=204)
def delete_category(item_id: ItemId, session: DbSession, user: CurrentUser) -> None:
    category = get_owned_or_404(session, Category, item_id, user.id, NOT_FOUND)
    usage = _usage_count(session, item_id)
    if usage:
        raise conflict(
            f"Esta categoria é usada em {usage} lançamento(s), fixa(s) ou linha(s) de fatura. "
            "Arquive-a para escondê-la sem perder o histórico."
        )
    session.delete(category)
    session.commit()


def _validate(body: CategoryIn, session: Session, user_id: int, exclude_id: int | None = None) -> None:
    if body.kind is Kind.EXPENSE and body.default_bucket is None:
        raise invalid("default_bucket", "Escolha o grupo do orçamento: necessidade, desejo ou poupança.")
    if body.kind is Kind.INCOME and body.default_bucket is not None:
        raise invalid("default_bucket", "Categorias de receita não entram nos grupos do orçamento.")
    ensure_unique_name(
        session,
        Category,
        body.name,
        "Já existe uma categoria com esse nome.",
        user_id=user_id,
        exclude_id=exclude_id,
    )


def _usage_count(session: Session, category_id: int) -> int:
    return count_references(
        session,
        Transaction.category_id == category_id,
        RecurringRule.category_id == category_id,
        InvoiceLine.category_id == category_id,
    )

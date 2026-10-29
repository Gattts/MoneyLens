"""Tudo o que é de um usuário passa por aqui: consultas filtradas pelo dono e busca por id só entre os seus.

Um item de outro usuário responde como um id inexistente (404 ou "não encontrado"), sem revelar que existe.
"""

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from financeiro.errors import not_found
from financeiro.models import (
    BudgetSettings,
    CardPayment,
    Category,
    CategoryRule,
    CreditCard,
    ForecastModel,
    Goal,
    InvoiceImport,
    InvoiceLine,
    RecurringRule,
    Transaction,
)

OwnedModel = (
    BudgetSettings
    | CardPayment
    | Category
    | CategoryRule
    | CreditCard
    | ForecastModel
    | Goal
    | InvoiceImport
    | RecurringRule
    | Transaction
)


def owned[M: OwnedModel](model: type[M], user_id: int) -> Select[M]:
    return select(model).where(model.user_id == user_id)


def get_owned[M: OwnedModel](session: Session, model: type[M], item_id: int, user_id: int) -> M | None:
    return session.scalar(owned(model, user_id).where(model.id == item_id))


def get_owned_or_404[M: OwnedModel](
    session: Session, model: type[M], item_id: int, user_id: int, message: str
) -> M:
    item = get_owned(session, model, item_id, user_id)
    if item is None:
        raise not_found(message)
    return item


def get_owned_line_or_404(session: Session, item_id: int, user_id: int, message: str) -> InvoiceLine:
    """Linha de fatura do usuário: o dono vem da importação a que ela pertence."""
    line = session.scalar(
        select(InvoiceLine)
        .join(InvoiceImport, InvoiceImport.id == InvoiceLine.import_id)
        .where(InvoiceLine.id == item_id, InvoiceImport.user_id == user_id)
    )
    if line is None:
        raise not_found(message)
    return line

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from financeiro.db import DbSession
from financeiro.deps import get_today
from financeiro.domain.cards import invoice_month_for
from financeiro.errors import conflict
from financeiro.models import CardPayment, CreditCard, InvoiceImport, RecurringRule, Transaction
from financeiro.schemas.cards import CardIn, CardOut, CardPaymentIn, InvoiceOut
from financeiro.schemas.common import ItemId, Month
from financeiro.security import CurrentUser
from financeiro.services.card_payments import delete_payment, record_manual_payment
from financeiro.services.cards import card_out, invoice_detail
from financeiro.services.lookup import count_references, ensure_unique_name, name_key
from financeiro.services.ownership import get_owned_or_404, owned

router = APIRouter(prefix="/cards", tags=["cartões"])
payments_router = APIRouter(prefix="/card-payments", tags=["cartões"])

NOT_FOUND = "Cartão não encontrado."
PAYMENT_NOT_FOUND = "Pagamento não encontrado."
DUPLICATE_NAME = "Já existe um cartão com esse nome."
Today = Annotated[date, Depends(get_today)]


@router.get("")
def list_cards(session: DbSession, user: CurrentUser, today: Today) -> list[CardOut]:
    cards = sorted(
        session.scalars(owned(CreditCard, user.id)).all(), key=lambda c: (c.archived, name_key(c.name))
    )
    return [card_out(session, card, today) for card in cards]


@router.post("", status_code=201)
def create_card(body: CardIn, session: DbSession, today: Today, user: CurrentUser) -> CardOut:
    ensure_unique_name(session, CreditCard, body.name, DUPLICATE_NAME, user_id=user.id)
    card = CreditCard(**body.model_dump(), user_id=user.id, payments_since=today)
    session.add(card)
    session.commit()
    return card_out(session, card, today)


@router.put("/{item_id}")
def update_card(
    item_id: ItemId, body: CardIn, session: DbSession, user: CurrentUser, today: Today
) -> CardOut:
    card = get_owned_or_404(session, CreditCard, item_id, user.id, NOT_FOUND)
    ensure_unique_name(session, CreditCard, body.name, DUPLICATE_NAME, user_id=user.id, exclude_id=item_id)
    for field, value in body.model_dump().items():
        setattr(card, field, value)
    session.commit()
    return card_out(session, card, today)


@router.delete("/{item_id}", status_code=204)
def delete_card(item_id: ItemId, session: DbSession, user: CurrentUser) -> None:
    card = get_owned_or_404(session, CreditCard, item_id, user.id, NOT_FOUND)
    usage = _usage_count(session, item_id)
    if usage:
        raise conflict(
            f"Este cartão tem {usage} lançamento(s), fixa(s), fatura(s) importada(s) ou pagamento(s). "
            "Arquive-o para escondê-lo sem perder o histórico."
        )
    session.delete(card)
    session.commit()


@router.delete("/{item_id}/invoice-password", status_code=204)
def forget_invoice_password(item_id: ItemId, session: DbSession, user: CurrentUser) -> None:
    get_owned_or_404(session, CreditCard, item_id, user.id, NOT_FOUND).invoice_password_encrypted = None
    session.commit()


@router.get("/{item_id}/invoice")
def get_invoice(
    item_id: ItemId,
    session: DbSession,
    user: CurrentUser,
    today: Today,
    month: Annotated[Month | None, Query()] = None,
) -> InvoiceOut:
    card = get_owned_or_404(session, CreditCard, item_id, user.id, NOT_FOUND)
    invoice_month = month or invoice_month_for(today, card.closing_day)
    return invoice_detail(session, card, invoice_month, today)


@router.post("/{item_id}/payments", status_code=201)
def pay_invoice(
    item_id: ItemId, body: CardPaymentIn, session: DbSession, user: CurrentUser, today: Today
) -> InvoiceOut:
    """Marca a fatura como paga (inteira ou em parte). Vale também para cartão arquivado."""
    card = get_owned_or_404(session, CreditCard, item_id, user.id, NOT_FOUND)
    record_manual_payment(session, card, body, today)
    return invoice_detail(session, card, body.invoice_month, today)


@payments_router.delete("/{item_id}", status_code=204)
def remove_payment(item_id: ItemId, session: DbSession, user: CurrentUser) -> None:
    delete_payment(session, get_owned_or_404(session, CardPayment, item_id, user.id, PAYMENT_NOT_FOUND))


def _usage_count(session: Session, card_id: int) -> int:
    return count_references(
        session,
        Transaction.card_id == card_id,
        RecurringRule.card_id == card_id,
        InvoiceImport.card_id == card_id,
        CardPayment.card_id == card_id,
    )

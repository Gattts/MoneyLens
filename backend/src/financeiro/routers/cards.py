from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from financeiro.db import DbSession
from financeiro.deps import get_today
from financeiro.domain.cards import invoice_month_for
from financeiro.errors import conflict
from financeiro.models import CreditCard, RecurringRule, Transaction
from financeiro.schemas.cards import CardIn, CardOut, InvoiceOut
from financeiro.schemas.common import ItemId, Month
from financeiro.services.cards import card_out, invoice_detail
from financeiro.services.lookup import count_references, ensure_unique_name, get_or_404, name_key

router = APIRouter(prefix="/cards", tags=["cartões"])

NOT_FOUND = "Cartão não encontrado."
DUPLICATE_NAME = "Já existe um cartão com esse nome."
Today = Annotated[date, Depends(get_today)]


@router.get("")
def list_cards(session: DbSession, today: Today) -> list[CardOut]:
    cards = sorted(session.scalars(select(CreditCard)).all(), key=lambda c: (c.archived, name_key(c.name)))
    return [card_out(session, card, today) for card in cards]


@router.post("", status_code=201)
def create_card(body: CardIn, session: DbSession, today: Today) -> CardOut:
    ensure_unique_name(session, CreditCard, body.name, DUPLICATE_NAME)
    card = CreditCard(**body.model_dump())
    session.add(card)
    session.commit()
    return card_out(session, card, today)


@router.put("/{item_id}")
def update_card(item_id: ItemId, body: CardIn, session: DbSession, today: Today) -> CardOut:
    card = get_or_404(session, CreditCard, item_id, NOT_FOUND)
    ensure_unique_name(session, CreditCard, body.name, DUPLICATE_NAME, exclude_id=item_id)
    for field, value in body.model_dump().items():
        setattr(card, field, value)
    session.commit()
    return card_out(session, card, today)


@router.delete("/{item_id}", status_code=204)
def delete_card(item_id: ItemId, session: DbSession) -> None:
    card = get_or_404(session, CreditCard, item_id, NOT_FOUND)
    usage = _usage_count(session, item_id)
    if usage:
        raise conflict(
            f"Este cartão tem {usage} lançamento(s) ou fixa(s). "
            "Arquive-o para escondê-lo sem perder o histórico."
        )
    session.delete(card)
    session.commit()


@router.get("/{item_id}/invoice")
def get_invoice(
    item_id: ItemId,
    session: DbSession,
    today: Today,
    month: Annotated[Month | None, Query()] = None,
) -> InvoiceOut:
    card = get_or_404(session, CreditCard, item_id, NOT_FOUND)
    invoice_month = month or invoice_month_for(today, card.closing_day)
    return invoice_detail(session, card, invoice_month, today)


def _usage_count(session: Session, card_id: int) -> int:
    return count_references(session, Transaction.card_id == card_id, RecurringRule.card_id == card_id)

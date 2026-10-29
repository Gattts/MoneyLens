from enum import StrEnum
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Query
from sqlalchemy import delete

from financeiro.db import DbSession
from financeiro.domain.enums import Kind, PaymentMethod
from financeiro.domain.installments import installment_dates, split_amount
from financeiro.domain.months import month_bounds
from financeiro.errors import invalid
from financeiro.models import Transaction
from financeiro.schemas.common import MAX_DATE, MAX_ID, ItemId, Month
from financeiro.schemas.transactions import TransactionCreate, TransactionIn, TransactionOut
from financeiro.security import CurrentUser
from financeiro.services.entries import check_goal, check_payment, resolve_bucket
from financeiro.services.ownership import get_owned_or_404, owned

router = APIRouter(prefix="/transactions", tags=["lançamentos"])

NOT_FOUND = "Lançamento não encontrado."
OptionalId = Annotated[int | None, Query(gt=0, le=MAX_ID)]


class DeleteScope(StrEnum):
    ONE = "one"
    INSTALLMENTS = "installments"


# Cartão parcela na fatura; Pix e boleto parcelados debitam uma parcela por mês da conta.
INSTALLMENT_METHODS = (PaymentMethod.CREDIT_CARD, PaymentMethod.PIX, PaymentMethod.BANK_SLIP)


@router.get("")
def list_transactions(
    session: DbSession,
    user: CurrentUser,
    *,
    month: Annotated[Month | None, Query()] = None,
    kind: Kind | None = None,
    category_id: OptionalId = None,
    card_id: OptionalId = None,
    goal_id: OptionalId = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
) -> list[TransactionOut]:
    query = owned(Transaction, user.id)
    if month is not None:
        start, end = month_bounds(month)
        query = query.where(Transaction.date >= start, Transaction.date < end)
    if kind is not None:
        query = query.where(Transaction.kind == kind)
    if category_id is not None:
        query = query.where(Transaction.category_id == category_id)
    if card_id is not None:
        query = query.where(Transaction.card_id == card_id)
    if goal_id is not None:
        query = query.where(Transaction.goal_id == goal_id)
    if q and q.strip():
        query = query.where(Transaction.description.ilike(f"%{_escape_like(q.strip())}%", escape="\\"))
    rows = session.scalars(query.order_by(Transaction.date.desc(), Transaction.id.desc()).limit(limit)).all()
    return [TransactionOut.model_validate(row) for row in rows]


@router.post("", status_code=201)
def create_transactions(
    body: TransactionCreate, session: DbSession, user: CurrentUser
) -> list[TransactionOut]:
    bucket = resolve_bucket(
        session, user_id=user.id, kind=body.kind, category_id=body.category_id, bucket=body.bucket
    )
    check_payment(
        session, user_id=user.id, kind=body.kind, payment_method=body.payment_method, card_id=body.card_id
    )
    check_goal(session, user_id=user.id, goal_id=body.goal_id, bucket=bucket)
    if body.installments > 1 and body.payment_method not in INSTALLMENT_METHODS:
        raise invalid("installments", "Parcelamento só existe no cartão de crédito, no Pix e no boleto.")
    try:
        amounts = split_amount(body.amount_cents, body.installments)
    except ValueError as error:
        raise invalid("amount_cents", str(error)) from error
    dates = installment_dates(body.date, body.installments)
    if dates[-1] > MAX_DATE:
        raise invalid("installments", "As parcelas passariam de 2100. Reduza o número de parcelas.")

    group = uuid4().hex if body.installments > 1 else None
    common = body.model_dump(exclude={"installments", "amount_cents", "date", "bucket"})
    created = [
        Transaction(
            user_id=user.id,
            **common,
            bucket=bucket,
            amount_cents=amount,
            date=day,
            installment_group=group,
            installment_number=number if group else None,
            installment_total=body.installments if group else None,
        )
        for number, (amount, day) in enumerate(zip(amounts, dates, strict=True), start=1)
    ]
    session.add_all(created)
    session.commit()
    return [TransactionOut.model_validate(transaction) for transaction in created]


@router.put("/{item_id}")
def update_transaction(
    item_id: ItemId, body: TransactionIn, session: DbSession, user: CurrentUser
) -> TransactionOut:
    transaction = get_owned_or_404(session, Transaction, item_id, user.id, NOT_FOUND)
    bucket = resolve_bucket(
        session,
        user_id=user.id,
        kind=body.kind,
        category_id=body.category_id,
        bucket=body.bucket,
        current_category_id=transaction.category_id,
    )
    check_payment(
        session,
        user_id=user.id,
        kind=body.kind,
        payment_method=body.payment_method,
        card_id=body.card_id,
        current_card_id=transaction.card_id,
    )
    check_goal(
        session, user_id=user.id, goal_id=body.goal_id, bucket=bucket, current_goal_id=transaction.goal_id
    )
    moved = (body.payment_method, body.card_id) != (transaction.payment_method, transaction.card_id)
    if transaction.installment_group and moved:
        raise invalid(
            "payment_method",
            "As parcelas ficam no mesmo cartão. Para trocar, exclua a compra e lance de novo.",
        )
    for field, value in body.model_dump(exclude={"bucket"}).items():
        setattr(transaction, field, value)
    transaction.bucket = bucket
    session.commit()
    return TransactionOut.model_validate(transaction)


@router.delete("/{item_id}", status_code=204)
def delete_transaction(
    item_id: ItemId, session: DbSession, user: CurrentUser, scope: DeleteScope = DeleteScope.ONE
) -> None:
    transaction = get_owned_or_404(session, Transaction, item_id, user.id, NOT_FOUND)
    if scope is DeleteScope.INSTALLMENTS and transaction.installment_group:
        session.execute(
            delete(Transaction).where(
                Transaction.user_id == user.id, Transaction.installment_group == transaction.installment_group
            )
        )
    else:
        session.delete(transaction)
    session.commit()


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

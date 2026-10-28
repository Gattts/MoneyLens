from datetime import date

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from financeiro.db import DbSession
from financeiro.domain.enums import Bucket
from financeiro.domain.recurrence import occurrence_date, occurs_in
from financeiro.errors import conflict, invalid
from financeiro.models import RecurringRule, Transaction
from financeiro.schemas.common import ItemId
from financeiro.schemas.recurring import ConfirmIn, RecurringIn, RecurringOut
from financeiro.schemas.transactions import TransactionOut
from financeiro.services.entries import check_payment, resolve_bucket
from financeiro.services.lookup import get_or_404, name_key

router = APIRouter(prefix="/recurring", tags=["fixas"])

NOT_FOUND = "Fixa não encontrada."


@router.get("")
def list_rules(session: DbSession) -> list[RecurringOut]:
    rules = session.scalars(select(RecurringRule)).all()
    ordered = sorted(rules, key=lambda r: (r.kind, r.day_of_month, name_key(r.description)))
    return [RecurringOut.model_validate(rule) for rule in ordered]


@router.post("", status_code=201)
def create_rule(body: RecurringIn, session: DbSession) -> RecurringOut:
    rule = RecurringRule(**body.model_dump(exclude={"bucket"}), bucket=_validate(body, session))
    session.add(rule)
    session.commit()
    return RecurringOut.model_validate(rule)


@router.put("/{item_id}")
def update_rule(item_id: ItemId, body: RecurringIn, session: DbSession) -> RecurringOut:
    rule = get_or_404(session, RecurringRule, item_id, NOT_FOUND)
    bucket = _validate(body, session, current=rule)
    for field, value in body.model_dump(exclude={"bucket"}).items():
        setattr(rule, field, value)
    rule.bucket = bucket
    session.commit()
    return RecurringOut.model_validate(rule)


@router.delete("/{item_id}", status_code=204)
def delete_rule(item_id: ItemId, session: DbSession) -> None:
    # Lançamentos já confirmados ficam no histórico; o banco limpa o vínculo (ON DELETE SET NULL).
    session.delete(get_or_404(session, RecurringRule, item_id, NOT_FOUND))
    session.commit()


@router.post("/{item_id}/confirm", status_code=201)
def confirm_occurrence(item_id: ItemId, body: ConfirmIn, session: DbSession) -> TransactionOut:
    rule = get_or_404(session, RecurringRule, item_id, NOT_FOUND)
    if not occurs_in(rule.start_month, rule.end_month, body.month):
        raise invalid("month", "Esta fixa não acontece nesse mês.")
    duplicate = conflict(f"Esta fixa já foi confirmada em {body.month:%m/%Y}.")
    if _already_confirmed(session, rule.id, body.month):
        raise duplicate
    transaction = Transaction(
        description=rule.description,
        kind=rule.kind,
        amount_cents=body.amount_cents or rule.amount_cents,
        date=body.date or occurrence_date(body.month, rule.day_of_month),
        category_id=rule.category_id,
        bucket=rule.bucket,
        payment_method=rule.payment_method,
        card_id=rule.card_id,
        notes=rule.notes,
        recurring_rule_id=rule.id,
        recurrence_month=body.month,
    )
    session.add(transaction)
    try:
        session.commit()
    except IntegrityError as error:
        # Duas confirmações quase simultâneas passam pela checagem acima; a restrição única do banco barra
        # a segunda, e a pessoa recebe a mesma mensagem de sempre.
        session.rollback()
        if _already_confirmed(session, rule.id, body.month):
            raise duplicate from error
        raise
    return TransactionOut.model_validate(transaction)


def _already_confirmed(session: Session, rule_id: int, month: date) -> bool:
    query = select(Transaction.id).where(
        Transaction.recurring_rule_id == rule_id, Transaction.recurrence_month == month
    )
    return session.scalar(query) is not None


def _validate(body: RecurringIn, session: Session, current: RecurringRule | None = None) -> Bucket | None:
    if body.end_month is not None and body.end_month < body.start_month:
        raise invalid("end_month", "O mês final precisa ser igual ou posterior ao mês inicial.")
    bucket = resolve_bucket(
        session,
        kind=body.kind,
        category_id=body.category_id,
        bucket=body.bucket,
        current_category_id=current.category_id if current else None,
    )
    check_payment(
        session,
        kind=body.kind,
        payment_method=body.payment_method,
        card_id=body.card_id,
        current_card_id=current.card_id if current else None,
    )
    return bucket

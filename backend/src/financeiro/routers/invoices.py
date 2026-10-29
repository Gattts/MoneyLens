import logging
from typing import Annotated

from fastapi import APIRouter, File, Form, Request, Response, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from financeiro.db import DbSession
from financeiro.domain.enums import ImportSource
from financeiro.domain.invoices import ParsedInvoice
from financeiro.domain.statements import ParsedStatement
from financeiro.errors import invalid
from financeiro.models import CreditCard, InvoiceImport
from financeiro.schemas.common import MAX_ID, ItemId
from financeiro.schemas.invoices import (
    InvoiceImportDetailOut,
    InvoiceImportListOut,
    LinePaymentIn,
    LineUpdateIn,
)
from financeiro.security import CurrentUser, load_secret_key
from financeiro.services.card_payments import register_line_payment
from financeiro.services.invoices.importer import import_invoice
from financeiro.services.invoices.learning import ignore_line, include_line, resolve_line
from financeiro.services.invoices.pdf import read_pdf_text
from financeiro.services.invoices.posting import confirm_import, undo_import
from financeiro.services.invoices.reader import UNKNOWN_DOCUMENT, parse_as
from financeiro.services.invoices.statement_importer import import_statement
from financeiro.services.invoices.views import import_detail, import_out, standby_totals
from financeiro.services.ownership import get_owned, get_owned_line_or_404, get_owned_or_404, owned
from financeiro.services.secret_box import seal, unseal

imports_router = APIRouter(prefix="/invoice-imports", tags=["faturas"])
lines_router = APIRouter(prefix="/invoice-lines", tags=["faturas"])
logger = logging.getLogger(__name__)

NOT_FOUND = "Fatura não encontrada."
LINE_NOT_FOUND = "Linha da fatura não encontrada."
MAX_PASSWORD_LENGTH = 100


@imports_router.post("", status_code=201)
def upload_invoice(
    *,
    request: Request,
    response: Response,
    session: DbSession,
    user: CurrentUser,
    file: Annotated[UploadFile, File()],
    source: Annotated[ImportSource, Form()] = ImportSource.CARD_INVOICE,
    card_id: Annotated[int | None, Form(gt=0, le=MAX_ID)] = None,
    password: Annotated[str | None, Form(max_length=MAX_PASSWORD_LENGTH)] = None,
    save_password: Annotated[bool, Form()] = False,
) -> InvoiceImportDetailOut:
    """Lê o PDF em memória (nada do arquivo nem da senha é gravado, exceto a senha cifrada se pedido).

    A fatura precisa do cartão; o extrato não usa cartão, e a senha dele serve só para a leitura.
    """
    card = _active_card(session, card_id, user.id) if source is ImportSource.CARD_INVOICE else None
    secret_key = load_secret_key(request.app.state.settings)
    sealed = card.invoice_password_encrypted if card else None
    saved = unseal(sealed, secret_key) if sealed else None
    pdf = read_pdf_text(file.file.read(), password=password or None, saved_password=saved)
    parsed = parse_as(pdf.text, source)
    if isinstance(parsed, ParsedStatement):
        invoice, created = import_statement(session, user.id, parsed)
    elif isinstance(parsed, ParsedInvoice) and card is not None:
        invoice, created = import_invoice(session, card, parsed)
        if save_password and password and pdf.opened_with == password:
            card.invoice_password_encrypted = seal(password, secret_key)
            session.commit()
    else:  # parse_as já recusa a combinação errada
        raise invalid("file", UNKNOWN_DOCUMENT)
    detail = import_detail(session, invoice)
    if not created:
        response.status_code = 200
        detail.already_imported = True
    logger.info("Fatura lida: %d linhas, %d pendentes", detail.line_count, detail.pending_count)
    return detail


@imports_router.get("")
def list_imports(session: DbSession, user: CurrentUser) -> InvoiceImportListOut:
    invoices = session.scalars(
        owned(InvoiceImport, user.id).order_by(
            func.coalesce(InvoiceImport.due_date, InvoiceImport.period_end).desc(), InvoiceImport.id.desc()
        )
    ).all()
    standby_count, standby_cents = standby_totals(session, user.id)
    return InvoiceImportListOut(
        imports=[import_out(session, invoice) for invoice in invoices],
        standby_count=standby_count,
        standby_cents=standby_cents,
    )


@imports_router.get("/{item_id}")
def get_import(item_id: ItemId, session: DbSession, user: CurrentUser) -> InvoiceImportDetailOut:
    return import_detail(session, get_owned_or_404(session, InvoiceImport, item_id, user.id, NOT_FOUND))


@imports_router.post("/{item_id}/confirm")
def confirm(item_id: ItemId, session: DbSession, user: CurrentUser) -> InvoiceImportDetailOut:
    invoice = get_owned_or_404(session, InvoiceImport, item_id, user.id, NOT_FOUND)
    confirm_import(session, invoice)
    return import_detail(session, invoice)


@imports_router.delete("/{item_id}", status_code=204)
def delete_import(item_id: ItemId, session: DbSession, user: CurrentUser) -> None:
    undo_import(session, get_owned_or_404(session, InvoiceImport, item_id, user.id, NOT_FOUND))


@lines_router.put("/{item_id}")
def update_line(
    item_id: ItemId, body: LineUpdateIn, session: DbSession, user: CurrentUser
) -> InvoiceImportDetailOut:
    line = get_owned_line_or_404(session, item_id, user.id, LINE_NOT_FOUND)
    resolve_line(session, line, body.category_id, remember=body.remember)
    return import_detail(session, session.get_one(InvoiceImport, line.import_id))


@lines_router.post("/{item_id}/include")
def include(item_id: ItemId, session: DbSession, user: CurrentUser) -> InvoiceImportDetailOut:
    line = get_owned_line_or_404(session, item_id, user.id, LINE_NOT_FOUND)
    include_line(session, line)
    return import_detail(session, session.get_one(InvoiceImport, line.import_id))


@lines_router.post("/{item_id}/ignore")
def ignore(item_id: ItemId, session: DbSession, user: CurrentUser) -> InvoiceImportDetailOut:
    line = get_owned_line_or_404(session, item_id, user.id, LINE_NOT_FOUND)
    ignore_line(session, line)
    return import_detail(session, session.get_one(InvoiceImport, line.import_id))


@lines_router.post("/{item_id}/card-payment")
def register_payment(
    item_id: ItemId, body: LinePaymentIn, session: DbSession, user: CurrentUser
) -> InvoiceImportDetailOut:
    """Confirma a linha do extrato como pagamento de uma fatura (não vira despesa)."""
    line = get_owned_line_or_404(session, item_id, user.id, LINE_NOT_FOUND)
    register_line_payment(
        session, line, user_id=user.id, card_id=body.card_id, invoice_month=body.invoice_month
    )
    return import_detail(session, session.get_one(InvoiceImport, line.import_id))


def _active_card(session: Session, card_id: int | None, user_id: int) -> CreditCard:
    if card_id is None:
        raise invalid("card_id", "Escolha o cartão.")
    card = get_owned(session, CreditCard, card_id, user_id)
    if card is None:
        raise invalid("card_id", "Cartão não encontrado.")
    if card.archived:
        raise invalid("card_id", "Este cartão está arquivado. Escolha outro ou desarquive-o.")
    return card

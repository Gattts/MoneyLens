import logging
from typing import Annotated

from fastapi import APIRouter, File, Form, Request, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from financeiro.db import DbSession
from financeiro.errors import invalid
from financeiro.models import CreditCard, InvoiceImport, InvoiceLine
from financeiro.schemas.common import MAX_ID, ItemId
from financeiro.schemas.invoices import InvoiceImportDetailOut, InvoiceImportListOut, LineUpdateIn
from financeiro.security import load_secret_key
from financeiro.services.invoices.importer import import_invoice
from financeiro.services.invoices.learning import include_line, resolve_line
from financeiro.services.invoices.pdf import read_pdf_text
from financeiro.services.invoices.posting import confirm_import, undo_import
from financeiro.services.invoices.reader import parse_invoice
from financeiro.services.invoices.views import import_detail, import_out, standby_totals
from financeiro.services.lookup import get_or_404
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
    card_id: Annotated[int, Form(gt=0, le=MAX_ID)],
    file: Annotated[UploadFile, File()],
    password: Annotated[str | None, Form(max_length=MAX_PASSWORD_LENGTH)] = None,
    save_password: Annotated[bool, Form()] = False,
) -> InvoiceImportDetailOut:
    """Lê o PDF em memória (nada do arquivo nem da senha é gravado, exceto a senha cifrada se pedido)."""
    card = _active_card(session, card_id)
    secret_key = load_secret_key(request.app.state.settings)
    saved = unseal(card.invoice_password_encrypted, secret_key) if card.invoice_password_encrypted else None
    pdf = read_pdf_text(file.file.read(), password=password or None, saved_password=saved)
    invoice, created = import_invoice(session, card, parse_invoice(pdf.text))
    if save_password and password and pdf.opened_with == password:
        card.invoice_password_encrypted = seal(password, secret_key)
        session.commit()
    detail = import_detail(session, invoice)
    if not created:
        response.status_code = 200
        detail.already_imported = True
    logger.info("Fatura lida: %d linhas, %d pendentes", detail.line_count, detail.pending_count)
    return detail


@imports_router.get("")
def list_imports(session: DbSession) -> InvoiceImportListOut:
    invoices = session.scalars(
        select(InvoiceImport).order_by(InvoiceImport.due_date.desc(), InvoiceImport.id.desc())
    ).all()
    standby_count, standby_cents = standby_totals(session)
    return InvoiceImportListOut(
        imports=[import_out(session, invoice) for invoice in invoices],
        standby_count=standby_count,
        standby_cents=standby_cents,
    )


@imports_router.get("/{item_id}")
def get_import(item_id: ItemId, session: DbSession) -> InvoiceImportDetailOut:
    return import_detail(session, get_or_404(session, InvoiceImport, item_id, NOT_FOUND))


@imports_router.post("/{item_id}/confirm")
def confirm(item_id: ItemId, session: DbSession) -> InvoiceImportDetailOut:
    invoice = get_or_404(session, InvoiceImport, item_id, NOT_FOUND)
    confirm_import(session, invoice)
    return import_detail(session, invoice)


@imports_router.delete("/{item_id}", status_code=204)
def delete_import(item_id: ItemId, session: DbSession) -> None:
    undo_import(session, get_or_404(session, InvoiceImport, item_id, NOT_FOUND))


@lines_router.put("/{item_id}")
def update_line(item_id: ItemId, body: LineUpdateIn, session: DbSession) -> InvoiceImportDetailOut:
    line = get_or_404(session, InvoiceLine, item_id, LINE_NOT_FOUND)
    resolve_line(session, line, body.category_id, remember=body.remember)
    return import_detail(session, session.get_one(InvoiceImport, line.import_id))


@lines_router.post("/{item_id}/include")
def include(item_id: ItemId, session: DbSession) -> InvoiceImportDetailOut:
    line = get_or_404(session, InvoiceLine, item_id, LINE_NOT_FOUND)
    include_line(session, line)
    return import_detail(session, session.get_one(InvoiceImport, line.import_id))


def _active_card(session: Session, card_id: int) -> CreditCard:
    card = session.get(CreditCard, card_id)
    if card is None:
        raise invalid("card_id", "Cartão não encontrado.")
    if card.archived:
        raise invalid("card_id", "Este cartão está arquivado. Escolha outro ou desarquive-o.")
    return card

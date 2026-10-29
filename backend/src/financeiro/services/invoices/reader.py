"""Escolhe o leitor pelo texto do PDF. Um banco novo é um módulo com `is_<banco>` e `parse_<banco>`."""

from collections.abc import Callable

from financeiro.domain.enums import ImportSource
from financeiro.domain.invoices import ParsedInvoice
from financeiro.domain.statements import ParsedStatement
from financeiro.errors import invalid
from financeiro.services.invoices.inter import is_inter, parse_inter
from financeiro.services.invoices.nubank import is_nubank_statement, parse_nubank

type ParsedDocument = ParsedInvoice | ParsedStatement

UNKNOWN_DOCUMENT = "Ainda não sei ler este arquivo. Por enquanto: fatura do Inter e extrato do Nubank."
STATEMENT_AS_INVOICE = "Este arquivo é um extrato de conta. Escolha Extrato da conta."
INVOICE_AS_STATEMENT = "Este arquivo é uma fatura de cartão. Escolha Fatura do cartão e o cartão."
READERS: tuple[tuple[Callable[[str], bool], Callable[[str], ParsedDocument]], ...] = (
    (is_inter, parse_inter),
    (is_nubank_statement, parse_nubank),
)


def parse_document(text: str) -> ParsedDocument:
    for accepts, parse in READERS:
        if accepts(text):
            return parse(text)
    raise invalid("file", UNKNOWN_DOCUMENT)


def parse_as(text: str, source: ImportSource) -> ParsedDocument:
    """Lê o documento e confere se é do tipo que a pessoa escolheu (fatura do cartão ou extrato da conta)."""
    parsed = parse_document(text)
    if source is ImportSource.CARD_INVOICE and isinstance(parsed, ParsedStatement):
        raise invalid("file", STATEMENT_AS_INVOICE)
    if source is ImportSource.ACCOUNT_STATEMENT and isinstance(parsed, ParsedInvoice):
        raise invalid("file", INVOICE_AS_STATEMENT)
    return parsed

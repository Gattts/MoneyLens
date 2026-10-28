"""Escolhe o leitor pelo banco da fatura. Um banco novo é um módulo com `is_<banco>` e `parse_<banco>`."""

from collections.abc import Callable

from financeiro.domain.invoices import ParsedInvoice
from financeiro.errors import invalid
from financeiro.services.invoices.inter import is_inter, parse_inter

READERS: tuple[tuple[Callable[[str], bool], Callable[[str], ParsedInvoice]], ...] = ((is_inter, parse_inter),)


def parse_invoice(text: str) -> ParsedInvoice:
    for accepts, parse in READERS:
        if accepts(text):
            return parse(text)
    raise invalid("file", "Por enquanto só leio faturas do Inter.")

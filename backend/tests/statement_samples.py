"""Extratos sintéticos no formato do extrato da conta Nubank, para os testes. Nenhum dado aqui é real.

Uso no E2E: `python -m tests.statement_samples <saída.pdf>` grava um extrato.
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path

from tests.invoice_samples import pdf_from_pages

TYPE_COLUMN = 19
COUNTERPARTY_COLUMN = 50
VALUE_COLUMN = 105
SUMMARY_LABEL_COLUMN = 60
SUMMARY_VALUE_COLUMN = 100
HOLDER = "ANA SOUZA"
PERIOD = ("01 DE OUTUBRO DE 2026", "27 DE OUTUBRO DE 2026")
PIX_OUT = "Transferência enviada pelo Pix"
PIX_IN = "Transferência recebida pelo Pix"
TRANSFER_IN = "Transferência Recebida"
APPLY = "Aplicação RDB"
REDEEM = "Resgate RDB"
CARD_PAYMENT = "Pagamento de fatura"
DEBIT = "Compra no débito"


@dataclass(frozen=True)
class Entry:
    kind: str  # o tipo como o banco imprime, ex. "Transferência enviada pelo Pix"
    counterparty: str  # primeira linha da coluna da contraparte ("" no RDB)
    value: str  # "1.234,56"
    extra: list[str] = field(default_factory=list)  # linhas de continuação da descrição


@dataclass(frozen=True)
class Day:
    date: str  # "01 OUT 2026"
    inflows: list[Entry] = field(default_factory=list)
    outflows: list[Entry] = field(default_factory=list)


def _pad(text: str, column: int) -> str:
    return text + " " * max(2, column - len(text))


def _cents(value: str) -> int:
    return int(value.replace(".", "").replace(",", ""))


def _brl(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    reais, centavos = divmod(abs(cents), 100)
    return sign + f"{reais:,}".replace(",", ".") + f",{centavos:02d}"


def pix_out(counterparty: str, value: str, document: str = "12.345.678/0001-90") -> Entry:
    """Pix enviado com a descrição em três linhas, como o Nubank imprime."""
    return Entry(
        PIX_OUT,
        f"{counterparty} - {document}",
        value,
        ["- BANCO EXEMPLO S.A. (0999) Agência: 1", "Conta: 1234-5"],
    )


def pix_in(counterparty: str, value: str, document: str = "•••.123.456-••") -> Entry:
    return Entry(
        PIX_IN,
        f"{counterparty} - {document}",
        value,
        ["- BANCO EXEMPLO S.A. (0999) Agência: 1", "Conta: 9876-5"],
    )


def _header(holder: str, period: tuple[str, str]) -> list[str]:
    return [
        _pad("", 70) + holder,
        _pad("", 60) + "CPF  •••.123.456-••  Agência  0001  Conta",
        _pad("", 90) + "1234567-8",
        "",
        _pad(f"{period[0]} a {period[1]}", 95) + "VALORES EM R$",
        "",
    ]


def _footer(page: int, pages: int, *, last: bool) -> list[str]:
    legal = [
        "O saldo líquido corresponde ao total de depósitos e rendimentos em conta.",
        _pad("Nu Financeira S.A. - Sociedade de Credito", 60) + "Nu Pagamentos S.A. - Instituição de",
        _pad("Investimento", 60) + "Pagamento",
        _pad("CNPJ: 00.000.000/0001-00", 60) + "CNPJ: 00.000.000/0001-00",
    ]
    return [
        "",
        *(legal if last else []),
        "Tem alguma dúvida? Mande uma mensagem para nosso time de atendimento pelo chat do app.",
        "Caso a solução fornecida não tenha sido satisfatória, fale com a Ouvidoria.",
        _pad("   Extrato gerado dia 28 de outubro de 2026 às 16:34", 95) + f"{page} de {pages}",
    ]


def _summary(opening: str, yield_: str, income: str, expense: str, closing: str) -> list[str]:
    def line(left: str, label: str, value: str) -> str:
        return _pad(_pad(left, SUMMARY_LABEL_COLUMN) + label, SUMMARY_VALUE_COLUMN) + value

    return [
        line("", "Saldo inicial", opening),
        line("Saldo final do período", "Rendimento líquido", yield_),
        line(f"R$ {closing}", "Total de entradas", f"+{income}"),
        line("", "Total de saídas", f"-{expense}"),
        line("", "Saldo final do período", closing),
        "",
        "Movimentações",
        "",
    ]


def _entry_lines(entry: Entry) -> list[str]:
    if entry.counterparty:
        first = _pad(
            _pad(_pad("", TYPE_COLUMN) + entry.kind, COUNTERPARTY_COLUMN) + entry.counterparty, VALUE_COLUMN
        )
    else:
        first = _pad(_pad("", TYPE_COLUMN) + entry.kind, VALUE_COLUMN)
    return [first + entry.value, *(_pad("", COUNTERPARTY_COLUMN) + extra for extra in entry.extra), ""]


def _movements(days: list[Day]) -> list[str]:
    lines: list[str] = []
    for day in days:
        first = True
        for label, sign, entries in (
            ("Total de entradas", "+", day.inflows),
            ("Total de saídas", "-", day.outflows),
        ):
            if not entries:
                continue
            total = _brl(sum(_cents(entry.value) for entry in entries))
            prefix = day.date if first else ""
            lines += [_pad(_pad(prefix, TYPE_COLUMN) + label, VALUE_COLUMN) + f"{sign} {total}", ""]
            first = False
            for entry in entries:
                lines += _entry_lines(entry)
        lines += [""]
    return lines


def statement_pages(
    days: list[Day],
    *,
    holder: str = HOLDER,
    opening: str = "100,00",
    yield_: str = "+0,00",
    income: str | None = None,
    expense: str | None = None,
    closing: str | None = None,
    period: tuple[str, str] = PERIOD,
    break_after: int | None = None,
) -> list[str]:
    """Texto de cada página. Totais vêm das linhas quando não informados (informar permite totais errados).

    `break_after` quebra a página depois da linha *n* das movimentações (no meio de um bloco ou de uma
    descrição).
    """
    entries = [(entry, True) for day in days for entry in day.inflows]
    entries += [(entry, False) for day in days for entry in day.outflows]
    income_cents = sum(_cents(entry.value) for entry, credit in entries if credit)
    expense_cents = sum(_cents(entry.value) for entry, credit in entries if not credit)
    opening_cents = -_cents(opening[1:]) if opening.startswith("-") else _cents(opening)
    income = income if income is not None else _brl(income_cents)
    expense = expense if expense is not None else _brl(expense_cents)
    closing = closing if closing is not None else _brl(opening_cents + income_cents - expense_cents)
    movements = _movements(days)
    cut = len(movements) if break_after is None else break_after
    chunks = [movements[:cut], movements[cut:]] if break_after is not None else [movements]
    pages = []
    for index, chunk in enumerate(chunks, start=1):
        body = _summary(opening, yield_, income, expense, closing) + chunk if index == 1 else chunk
        lines = _header(holder, period) + body + _footer(index, len(chunks), last=index == len(chunks))
        pages.append("\n".join(lines))
    return pages


def statement_text(days: list[Day], **options) -> str:
    """O texto como `read_pdf_text` devolve: as páginas unidas por quebra de linha."""
    return "\n".join(statement_pages(days, **options))


def statement_pdf(pages: list[str]) -> bytes:
    return pdf_from_pages([page.splitlines() for page in pages])


def upload_statement(client, pdf: bytes, **form: str):
    return client.post(
        "/api/invoice-imports",
        data={"source": "account_statement", **form},
        files={"file": ("extrato.pdf", pdf, "application/pdf")},
    )


E2E_DAYS = [
    Day("02 OUT 2026", inflows=[pix_in("EMPRESA EXEMPLO LTDA", "1.500,00", "11.222.333/0001-44")]),
    Day(
        "03 OUT 2026",
        outflows=[
            pix_out("PADARIA DO BAIRRO", "12,50"),
            pix_out("CARLOS PEREIRA", "37,00", "•••.987.654-••"),
        ],
    ),
]

if __name__ == "__main__":
    output = Path(sys.argv[1])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(statement_pdf(statement_pages(E2E_DAYS)))

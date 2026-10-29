"""Leitor do extrato da conta do Nubank, a partir do texto extraído do PDF no modo layout.

Cada página traz cabeçalho (titular, conta e período) e rodapé (atendimento e "Extrato gerado ... N de M");
os dois são descartados para que uma descrição quebrada entre páginas se junte. As movimentações vêm por dia,
em blocos "Total de entradas" e "Total de saídas". O valor de cada linha não tem sinal (vem do bloco).
Nada é aceito sem que os totais impressos confiram com a soma das linhas.
"""

import datetime as dt
import re
from dataclasses import dataclass, field

from financeiro.domain.enums import PaymentMethod
from financeiro.domain.statements import ParsedStatement, ParsedStatementLine, StatementNature
from financeiro.errors import invalid
from financeiro.services.invoices.text import FULL_MONTHS, VALUE, cents, plain

BANK = "nubank"
MISMATCH = "Não consegui conferir o extrato: os totais não batem. Nada foi importado."
NO_PERIOD = "Não encontrei o período do extrato."
MONTHS = {
    "JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6,
    "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12,
}  # fmt: skip
SIGNED = rf"(?P<sign>[+-])?\s?(?P<value>{VALUE})"
PERIOD_RE = re.compile(r"(\d{2}) DE ([A-ZÇ]+) DE (\d{4}) a (\d{2}) DE ([A-ZÇ]+) DE (\d{4})")
DAY_RE = re.compile(r"^(?P<day>\d{2}) (?P<month>[A-Z]{3}) (?P<year>\d{4})(?=\s|$)")
BLOCK_RE = re.compile(rf"^\s*Total de (?P<kind>entradas|saídas)\s+{SIGNED}\s*$")
ENTRY_RE = re.compile(rf"^\s*(?P<body>\S.*?)\s{{2,}}(?P<value>{VALUE})\s*$")
DOCUMENT_RE = re.compile(
    r"^(?:•••\.\d{3}\.\d{3}-••|\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{3}\.\d{3}\.\d{3}-\d{2})$"
)
SUMMARY_LABELS = {
    "opening": "Saldo inicial",
    "yield": "Rendimento líquido",
    "income": "Total de entradas",
    "expense": "Total de saídas",
    "closing": "Saldo final do período",
}
MOVEMENTS = "Movimentações"
FOOTER_STARTS = ("Tem alguma dúvida?", "O saldo líquido corresponde")
FOOTER_END = "Extrato gerado"
# Tipo impresso -> (natureza fixa, ou None para entrada/saída conforme o bloco; forma de pagamento).
TYPES: dict[str, tuple[StatementNature | None, PaymentMethod]] = {
    "transferência enviada pelo pix": (None, PaymentMethod.PIX),
    "transferência recebida pelo pix": (None, PaymentMethod.PIX),
    "transferência enviada": (None, PaymentMethod.TRANSFER),
    "transferência recebida": (None, PaymentMethod.TRANSFER),
    "compra no débito": (None, PaymentMethod.DEBIT),
    "aplicação rdb": (StatementNature.INVESTMENT, PaymentMethod.TRANSFER),
    "resgate rdb": (StatementNature.INVESTMENT, PaymentMethod.TRANSFER),
    "pagamento de fatura": (StatementNature.CARD_PAYMENT, PaymentMethod.TRANSFER),
}


@dataclass
class _Entry:
    date: dt.date
    type_text: str
    amount_cents: int
    raw: list[str] = field(default_factory=list)  # coluna da contraparte, linha a linha


@dataclass
class _Block:
    is_credit: bool
    total_cents: int
    entries: list[_Entry] = field(default_factory=list)


def is_nubank_statement(text: str) -> bool:
    folded = text.casefold()
    return "saldo final do período" in folded and "nu pagamentos" in folded


def parse_nubank(text: str) -> ParsedStatement:
    lines = text.splitlines()
    holder = next((line.strip() for line in lines if line.strip()), "")
    period, body = _strip_pages(lines)
    summary, movements = _split_summary(body)
    blocks = _blocks(movements)
    _check(summary, blocks)
    parsed = [
        _parsed_line(position, block, entry, holder)
        for position, (block, entry) in enumerate(
            ((block, entry) for block in blocks for entry in block.entries), start=1
        )
    ]
    return ParsedStatement(
        bank=BANK, holder=holder, period_start=period[0], period_end=period[1], lines=parsed
    )


def _strip_pages(lines: list[str]) -> tuple[tuple[dt.date, dt.date], list[str]]:
    """Tira cabeçalho e rodapé de cada página; devolve o período e as linhas que sobram, na ordem."""
    period: tuple[dt.date, dt.date] | None = None
    body: list[str] = []
    in_header, in_footer = True, False
    for line in lines:
        if in_header:
            if match := PERIOD_RE.search(line):
                period = period or _period(match)
                in_header = False
        elif in_footer:
            if FOOTER_END in line:
                in_footer, in_header = False, True
        elif line.strip().startswith(FOOTER_STARTS):
            in_footer = True
        else:
            body.append(line)
    if period is None:
        raise invalid("file", NO_PERIOD)
    return period, body


def _period(match: re.Match[str]) -> tuple[dt.date, dt.date]:
    start_day, start_month, start_year, end_day, end_month, end_year = match.groups()
    try:
        start = dt.date(int(start_year), FULL_MONTHS[start_month], int(start_day))
        end = dt.date(int(end_year), FULL_MONTHS[end_month], int(end_day))
    except (KeyError, ValueError) as error:
        raise invalid("file", NO_PERIOD) from error
    return start, end


def _split_summary(body: list[str]) -> tuple[dict[str, int], list[str]]:
    marker = next((index for index, line in enumerate(body) if line.strip() == MOVEMENTS), len(body))
    summary_text = "\n".join(body[:marker])
    summary: dict[str, int] = {}
    for key, label in SUMMARY_LABELS.items():
        match = re.search(rf"{label}[ \t]+{SIGNED}(?=\s|$)", summary_text)
        if match is None:
            raise invalid("file", MISMATCH)
        summary[key] = _signed(match)
    return summary, body[marker + 1 :]


def _blocks(lines: list[str]) -> list[_Block]:
    blocks: list[_Block] = []
    current: dt.date | None = None
    for raw in lines:
        line = raw
        if day := DAY_RE.match(raw):
            current = _day(day)
            line = raw[day.end() :]
        if not line.strip():
            continue
        if block := BLOCK_RE.match(line):
            if current is None:
                raise invalid("file", MISMATCH)
            blocks.append(_Block(is_credit=block["kind"] == "entradas", total_cents=abs(_signed(block))))
        elif entry := ENTRY_RE.match(line):
            if not blocks or current is None:
                raise invalid("file", MISMATCH)
            type_text, *rest = re.split(r"\s{2,}", entry["body"].strip())
            blocks[-1].entries.append(_Entry(current, type_text, cents(entry["value"]), rest))
        elif blocks and blocks[-1].entries:
            blocks[-1].entries[-1].raw.append(line.strip())  # continuação da descrição
    return blocks


def _day(match: re.Match[str]) -> dt.date:
    try:
        return dt.date(int(match["year"]), MONTHS[match["month"]], int(match["day"]))
    except (KeyError, ValueError) as error:
        raise invalid("file", MISMATCH) from error


def _check(summary: dict[str, int], blocks: list[_Block]) -> None:
    if any(sum(entry.amount_cents for entry in block.entries) != block.total_cents for block in blocks):
        raise invalid("file", MISMATCH)
    income = sum(block.total_cents for block in blocks if block.is_credit)
    expense = sum(block.total_cents for block in blocks if not block.is_credit)
    if income != abs(summary["income"]) or expense != abs(summary["expense"]):
        raise invalid("file", MISMATCH)
    # Não há amostra com rendimento: ele pode já estar nas entradas ou vir à parte.
    expected = summary["opening"] + income - expense
    if summary["closing"] not in (expected, expected + summary["yield"]):
        raise invalid("file", MISMATCH)


def _parsed_line(position: int, block: _Block, entry: _Entry, holder: str) -> ParsedStatementLine:
    name = _counterparty(" ".join(entry.raw))
    known = TYPES.get(entry.type_text.casefold())
    fixed, method = known if known else (None, PaymentMethod.TRANSFER)
    if fixed is not None:
        nature, description = fixed, entry.type_text
    else:
        own = bool(name) and plain(name) == plain(holder)
        nature = StatementNature.OWN_TRANSFER if own else _direction(block.is_credit)
        description = (name or entry.type_text) if known else f"{entry.type_text} {name}".strip()
    return ParsedStatementLine(
        position=position,
        date=entry.date,
        nature=nature,
        is_credit=block.is_credit,
        counterparty=name,
        description=description,
        amount_cents=entry.amount_cents,
        payment_method=method,
    )


def _direction(is_credit: bool) -> StatementNature:
    return StatementNature.INFLOW if is_credit else StatementNature.OUTFLOW


def _counterparty(raw: str) -> str:
    """O nome vem antes do CPF/CNPJ; o resto é banco, agência e conta."""
    parts = [part.strip() for part in " ".join(raw.split()).split(" - ")]
    for index, part in enumerate(parts[1:], start=1):
        if DOCUMENT_RE.match(part):
            return " - ".join(parts[:index])
    return parts[0]


def _signed(match: re.Match[str]) -> int:
    amount = cents(match["value"])
    return -amount if match["sign"] == "-" else amount

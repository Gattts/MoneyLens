"""Leitor do extrato de conta do PicPay, a partir do texto extraído do PDF no modo layout.

Cada página traz cabeçalho (titular, CPF, agência e conta) e rodapé ("Documento emitido em ... N de M");
os dois são descartados. As movimentações vêm por dia, do mais recente para o mais antigo, e cada dia traz
o saldo ao final dele; um dia que continua na página seguinte repete o título. As colunas (tipo,
origem/destino e forma de pagamento) são lidas pela posição do título de cada página. O valor traz o sinal.

Compras "Com cartão" não mexem no saldo (vão para a fatura) e ficam de fora. "Com saldo + cartão" tira do
saldo só uma parte, que o PDF não imprime: é o que sobra na conta do dia. Nada é aceito sem que a cadeia de
saldos confira; o dia mais antigo não tem saldo anterior impresso e fica sem essa conferência.
"""

import datetime as dt
import re
from dataclasses import dataclass, field

from financeiro.domain.enums import PaymentMethod
from financeiro.domain.statements import ParsedStatement, ParsedStatementLine, StatementNature
from financeiro.errors import invalid
from financeiro.services.invoices.text import FULL_MONTHS, VALUE, cents, plain

BANK = "picpay"
MISMATCH = "Não consegui conferir o extrato: os saldos não batem. Nada foi importado."
NO_PERIOD = "Não encontrei o período do extrato."
MINUS = "−"  # o PicPay imprime o sinal de menos tipográfico
MONEY = rf"(?P<sign>[+{MINUS}-])?\s?R\$\s?(?P<value>{VALUE})"
PERIOD_RE = re.compile(r"(\d{1,2}) de ([a-zç]+) de (\d{4}) a\b.*?(\d{1,2}) de ([a-zç]+) de (\d{4})", re.S)
FINAL_RE = re.compile(rf"Saldo final do período.*?{MONEY}", re.S)
DAY_RE = re.compile(
    rf"^\s*(?P<day>\d{{1,2}}) de (?P<month>[a-zç]+) (?P<year>\d{{4}})\s+Saldo ao final do dia: {MONEY}\s*$"
)
ENTRY_RE = re.compile(rf"^\s*\d{{2}}:\d{{2}}\s{{2,}}(?P<body>\S.*?)\s{{2,}}{MONEY}\s*$")
HEADER_END_RE = re.compile(r"^\s*CPF:.*Conta:")
FOOTER_START = "Documento emitido em"
FOOTER_END_RE = re.compile(r"\b\d+ de \d+\s*$")
COLUMN_LABELS = ("Tipo", "Origem", "Forma de pagamento")  # nessa ordem: as colunas 0, 1 e 2 de cada linha
SEGMENT = re.compile(r"\S+(?: \S+)*")  # trechos separados por 2 ou mais espaços
TOLERANCE = 2  # o texto de uma coluna pode começar um pouco antes do título dela
MEI_RE = re.compile(r"^\d{2}\.\d{3}\.\d{3}\s+")  # nome de MEI vem depois da raiz do CNPJ
BALANCE, CARD, MIXED = "saldo", "cartão", "saldo + cartão"
REFUND = "compra estornada"
PAYMENT, CARD_INVOICE = "pagamento realizado", "fatura picpay card"
# Tipo impresso -> (natureza fixa, ou None para entrada/saída conforme o sinal; forma de pagamento).
TYPES: dict[str, tuple[StatementNature | None, PaymentMethod]] = {
    "pix enviado": (None, PaymentMethod.PIX),
    "pix recebido": (None, PaymentMethod.PIX),
    "compra realizada": (None, PaymentMethod.DEBIT),
    REFUND: (None, PaymentMethod.DEBIT),
    PAYMENT: (None, PaymentMethod.DEBIT),
    "dinheiro guardado": (StatementNature.INVESTMENT, PaymentMethod.TRANSFER),
    "dinheiro resgatado": (StatementNature.INVESTMENT, PaymentMethod.TRANSFER),
}


@dataclass
class _Entry:
    cents: int  # com sinal: negativo saiu da conta
    columns: tuple[list[str], list[str], list[str]] = field(default_factory=lambda: ([], [], []))

    def add(self, cells: list[tuple[int, str]]) -> None:
        for column, text in cells:
            self.columns[column].append(text)

    @property
    def kind(self) -> str:
        return " ".join(self.columns[0])

    @property
    def origin(self) -> str:
        return " ".join(self.columns[1])

    @property
    def source(self) -> str:
        """De onde saiu o dinheiro: do saldo, do cartão ou dos dois (só numa saída)."""
        method = " ".join(self.columns[2]).casefold()
        if CARD not in method:
            return BALANCE
        return MIXED if BALANCE in method and self.cents < 0 else CARD


@dataclass
class _Day:
    date: dt.date
    closing: int
    entries: list[_Entry] = field(default_factory=list)  # na ordem do PDF: a mais recente primeiro


def is_picpay_statement(text: str) -> bool:
    folded = text.casefold()
    return "picpay" in folded and "extrato de conta" in folded and "saldo ao final do dia" in folded


def parse_picpay(text: str) -> ParsedStatement:
    lines = text.splitlines()
    holder = next((line.strip() for line in lines if line.strip()), "")
    period_start, period_end = _period(text)
    body = _strip_pages(lines)
    if _count_days(body) != _count_days(lines):  # um cabeçalho ou rodapé que não terminou engoliu dias
        raise invalid("file", MISMATCH)
    settled = _settle(_days(body), _final(text))
    parsed = [
        _parsed_line(position, date, entry, amount, holder)
        for position, (date, entry, amount) in enumerate(settled, start=1)
    ]
    return ParsedStatement(
        bank=BANK, holder=holder, period_start=period_start, period_end=period_end, lines=parsed
    )


def _period(text: str) -> tuple[dt.date, dt.date]:
    match = PERIOD_RE.search(text)
    if match is None:
        raise invalid("file", NO_PERIOD)
    start_day, start_month, start_year, end_day, end_month, end_year = match.groups()
    try:
        start = dt.date(int(start_year), FULL_MONTHS[start_month.upper()], int(start_day))
        end = dt.date(int(end_year), FULL_MONTHS[end_month.upper()], int(end_day))
    except (KeyError, ValueError) as error:
        raise invalid("file", NO_PERIOD) from error
    return start, end


def _final(text: str) -> int:
    match = FINAL_RE.search(text)
    if match is None:
        raise invalid("file", MISMATCH)
    return _signed(match)


def _strip_pages(lines: list[str]) -> list[str]:
    """Tira cabeçalho e rodapé de cada página e devolve as linhas que sobram, na ordem."""
    body: list[str] = []
    in_header, in_footer = True, False
    for line in lines:
        if in_header:
            in_header = HEADER_END_RE.match(line) is None
        elif in_footer:
            if FOOTER_END_RE.search(line):
                in_footer, in_header = False, True
        elif line.strip().startswith(FOOTER_START):
            in_footer = True
        else:
            body.append(line)
    return body


def _count_days(lines: list[str]) -> int:
    return sum(DAY_RE.match(line) is not None for line in lines)


def _days(body: list[str]) -> list[_Day]:
    days: list[_Day] = []
    columns: tuple[int, ...] | None = None
    for line in body:
        if not line.strip():
            continue
        if day := DAY_RE.match(line):
            _add_day(days, _date(day), _signed(day))
        elif line.strip().startswith("Hora") and all(label in line for label in COLUMN_LABELS):
            columns = tuple(line.index(label) for label in COLUMN_LABELS)
        elif entry := ENTRY_RE.match(line):
            if not days or columns is None:
                raise invalid("file", MISMATCH)
            new = _Entry(_signed(entry))
            new.add(_cells(line, entry.start("body"), entry.end("body"), columns))
            days[-1].entries.append(new)
        elif days and days[-1].entries and columns is not None:
            days[-1].entries[-1].add(_cells(line, 0, len(line), columns))  # nome que quebrou de linha
    return days


def _add_day(days: list[_Day], date: dt.date, closing: int) -> None:
    if days and date == days[-1].date:  # o dia continua da página anterior
        if closing != days[-1].closing:
            raise invalid("file", MISMATCH)
        return
    if days and date > days[-1].date:
        raise invalid("file", MISMATCH)
    days.append(_Day(date, closing))


def _cells(line: str, start: int, end: int, columns: tuple[int, ...]) -> list[tuple[int, str]]:
    """Cada trecho da linha com a coluna em que começa."""
    cells = []
    for chunk in SEGMENT.finditer(line, start, end):
        column = max(
            (index for index, position in enumerate(columns) if position <= chunk.start() + TOLERANCE),
            default=0,
        )
        cells.append((column, chunk.group()))
    return cells


def _settle(days: list[_Day], final: int) -> list[tuple[dt.date, _Entry, int]]:
    """Confere a cadeia de saldos e devolve, da mais antiga para a mais recente, cada movimentação com
    quanto ela mexeu no saldo. Compras no cartão ficam de fora; as de saldo + cartão dividem o que sobra na
    conta do dia, a partir da mais antiga."""
    if days and days[0].closing != final:
        raise invalid("file", MISMATCH)
    settled: list[tuple[dt.date, _Entry, int]] = []
    previous: int | None = None
    for day in reversed(days):
        entries = day.entries[::-1]
        mixed_total = -sum(entry.cents for entry in entries if entry.source == MIXED)
        if previous is None:
            taken = mixed_total  # sem saldo anterior não há como saber a parte do saldo: vale o valor inteiro
        else:
            taken = previous + sum(entry.cents for entry in entries if entry.source == BALANCE) - day.closing
            if not 0 <= taken <= mixed_total:
                raise invalid("file", MISMATCH)
        for entry in entries:
            if entry.source == CARD:
                continue
            amount = entry.cents
            if entry.source == MIXED:
                amount = -min(taken, -entry.cents)
                taken += amount
            if amount:
                settled.append((day.date, entry, amount))
        previous = day.closing
    return settled


def _parsed_line(
    position: int, date: dt.date, entry: _Entry, amount: int, holder: str
) -> ParsedStatementLine:
    kind, name = entry.kind, _counterparty(entry.origin)
    known = TYPES.get(kind.casefold())
    fixed, method = known if known else (None, PaymentMethod.TRANSFER)
    if kind.casefold() == PAYMENT and name.casefold() == CARD_INVOICE:
        fixed, method = StatementNature.CARD_PAYMENT, PaymentMethod.TRANSFER
    nature: StatementNature
    if fixed is StatementNature.CARD_PAYMENT:
        nature, description, name = fixed, name, ""
    elif fixed is not None:
        nature, description, name = fixed, kind, ""
    else:
        own = bool(name) and plain(name) == plain(holder)
        nature = StatementNature.OWN_TRANSFER if own else _direction(amount > 0)
        if not known:
            description = f"{kind} {name}".strip()
        elif kind.casefold() == REFUND:
            description = f"Estorno {name}".strip()
        else:
            description = name or kind
    return ParsedStatementLine(
        position=position,
        date=date,
        nature=nature,
        is_credit=amount > 0,
        counterparty=name,
        description=description,
        amount_cents=abs(amount),
        payment_method=method,
    )


def _direction(is_credit: bool) -> StatementNature:
    return StatementNature.INFLOW if is_credit else StatementNature.OUTFLOW


def _counterparty(origin: str) -> str:
    return MEI_RE.sub("", " ".join(origin.split()))


def _date(match: re.Match[str]) -> dt.date:
    try:
        return dt.date(int(match["year"]), FULL_MONTHS[match["month"].upper()], int(match["day"]))
    except (KeyError, ValueError) as error:
        raise invalid("file", MISMATCH) from error


def _signed(match: re.Match[str]) -> int:
    amount = cents(match["value"])
    return -amount if match["sign"] in (MINUS, "-") else amount

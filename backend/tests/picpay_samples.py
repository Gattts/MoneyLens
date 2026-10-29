"""Extratos sintéticos no formato do extrato de conta PicPay, para os testes. Nenhum dado aqui é real."""

from dataclasses import dataclass, field

from tests.invoice_samples import pdf_from_pages

HOUR_COLUMN = 1
TYPE_COLUMN = 8
ORIGIN_COLUMN = 34
METHOD_COLUMN = 60
VALUE_COLUMN = 82
BALANCE_COLUMN = 62
HOLDER = "ANA SOUZA"
PERIOD = ("1 de outubro de 2026", "27 de outubro de 2026")
PIX_OUT, PIX_IN = "Pix enviado", "Pix recebido"
SAVED, REDEEMED = "Dinheiro guardado", "Dinheiro resgatado"
PURCHASE, REFUND, PAYMENT = "Compra realizada", "Compra estornada", "Pagamento realizado"
BALANCE, CARD, MIXED = "Com saldo", "Com cartão", "Com saldo + cartão"
CARD_INVOICE = "Fatura PicPay Card"
MINUS = "−"


@dataclass(frozen=True)
class Entry:
    kind: str  # o tipo como o PicPay imprime, ex. "Pix enviado"
    origin: str  # primeira linha da coluna Origem / Destino ("" quando vazia)
    cents: int  # com sinal: negativo saiu da conta
    method: str = ""  # a forma de pagamento ("" quando vazia)
    extra: list[str] = field(default_factory=list)  # continuação da origem
    time: str = "12:00"
    from_balance: int | None = None  # "Com saldo + cartão": quanto saiu do saldo (o PDF não imprime)


@dataclass(frozen=True)
class Day:
    date: str  # "27 de outubro 2026"
    entries: list[Entry]  # do mais recente para o mais antigo, como o PicPay imprime


def _pad(text: str, column: int) -> str:
    return text + " " * max(2, column - len(text))


def _cents(value: str) -> int:
    return int(value.replace(".", "").replace(",", ""))


def _signed(value: str) -> int:
    """Valor como "1,00" ou "-1,00" (com o menos comum ou o do PicPay) em centavos com sinal."""
    return -_cents(value[1:]) if value[:1] in (MINUS, "-") else _cents(value)


def _brl(cents: int) -> str:
    reais, centavos = divmod(abs(cents), 100)
    return f"{reais:,}".replace(",", ".") + f",{centavos:02d}"


def money(cents: int, *, signed: bool = False) -> str:
    sign = MINUS if cents < 0 else "+" if signed else ""
    return f"{sign}R$ {_brl(cents)}"


def spent(kind: str, origin: str, value: str, method: str = BALANCE, **options) -> Entry:
    return Entry(kind, origin, -_cents(value), method, **options)


def received(kind: str, origin: str, value: str, method: str = "", **options) -> Entry:
    return Entry(kind, origin, _cents(value), method, **options)


def _effect(entry: Entry) -> int:
    """Quanto a movimentação mexe no saldo: compra no cartão não mexe; saldo + cartão, só a parte do saldo."""
    if entry.method == MIXED:
        return -entry.from_balance if entry.from_balance is not None else entry.cents
    return 0 if entry.method == CARD else entry.cents


def _closings(days: list[Day], opening: int) -> dict[str, int]:
    closings, balance = {}, opening
    for day in reversed(days):
        balance += sum(_effect(entry) for entry in day.entries)
        closings[day.date] = balance
    return closings


def _header(holder: str, period: tuple[str, str] | None, final: int) -> list[str]:
    lines = [holder, "CPF: 000.000.000-00  Agência: 0001  Conta: 0000000-0", ""]
    if period is not None:
        lines += [
            "Extrato de conta",
            "",
            _pad("Período", 40) + "Saldo final do período",
            _pad(f"{period[0]} a", 40) + money(final),
            period[1],
            "",
        ]
    return lines


def _footer(page: int, pages: int) -> list[str]:
    return [
        "",
        _pad(_pad("Documento emitido em:", 24) + "PicPay Serviços S/A", 52) + "Dúvidas? Fale pelo chat.",
        _pad(_pad("28/10/2026 às 16:32", 24) + "CNPJ: 00.000.000/0001-00", 52)
        + _pad("Ouvidoria 0800 000 0000", 85)
        + f"{page} de {pages}",
    ]


def _day_header(date: str, closing: int) -> list[str]:
    columns = _pad(_pad(_pad("", HOUR_COLUMN) + "Hora", TYPE_COLUMN) + "Tipo", ORIGIN_COLUMN)
    columns = _pad(_pad(columns + "Origem / Destino", METHOD_COLUMN) + "Forma de pagamento", VALUE_COLUMN + 4)
    return [
        "",
        _pad(_pad("", HOUR_COLUMN) + date, BALANCE_COLUMN) + f"Saldo ao final do dia: {money(closing)}",
        "",
        columns + "Valor",
        "",
    ]


def _entry_lines(entry: Entry) -> list[str]:
    first = _pad(_pad(_pad("", HOUR_COLUMN) + entry.time, TYPE_COLUMN) + entry.kind, ORIGIN_COLUMN)
    first = _pad(_pad(first + entry.origin, METHOD_COLUMN) + entry.method, VALUE_COLUMN)
    extra = [_pad("", ORIGIN_COLUMN) + text for text in entry.extra]
    return [first + money(entry.cents, signed=True), *extra, ""]


def statement_pages(
    days: list[Day],
    *,
    holder: str = HOLDER,
    opening: str = "0,00",
    period: tuple[str, str] = PERIOD,
    closings: dict[str, str] | None = None,
    final: str | None = None,
    break_after: int | None = None,
) -> list[str]:
    """Texto de cada página. Os saldos do dia saem das movimentações (`closings` e `final` permitem errar).

    `break_after` quebra a página depois da movimentação *n*; o dia em andamento repete o título na página.
    """
    computed = _closings(days, _signed(opening))
    computed.update({date: _signed(value) for date, value in (closings or {}).items()})
    if final is not None:
        final_cents = _signed(final)
    else:
        final_cents = computed[days[0].date] if days else _signed(opening)
    bodies: list[list[str]] = [[]]
    count = 0
    for day in days:
        for index, entry in enumerate(day.entries):
            if count and count == break_after:
                bodies.append([])
            if index == 0 or not bodies[-1]:
                bodies[-1] += _day_header(day.date, computed[day.date])
            bodies[-1] += _entry_lines(entry)
            count += 1
    pages = []
    for number, body in enumerate(bodies, start=1):
        header = _header(holder, period if number == 1 else None, final_cents)
        pages.append("\n".join(header + body + _footer(number, len(bodies))))
    return pages


def statement_text(days: list[Day], **options) -> str:
    """O texto como `read_pdf_text` devolve: as páginas unidas por quebra de linha."""
    return "\n".join(statement_pages(days, **options))


def statement_pdf(pages: list[str]) -> bytes:
    return pdf_from_pages([page.splitlines() for page in pages])

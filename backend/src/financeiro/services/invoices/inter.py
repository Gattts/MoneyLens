"""Leitor da fatura do cartão do Banco Inter, a partir do texto extraído do PDF no modo layout."""

import datetime as dt
import re

from financeiro.domain.invoices import CardSection, ParsedInvoice, ParsedLine
from financeiro.domain.merchants import merchant_key
from financeiro.errors import invalid

MONTHS = {
    "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12,
}  # fmt: skip
VALUE = r"\d{1,3}(?:\.\d{3})*,\d{2}"
# A descrição é gulosa e o beneficiário é a última coluna antes do valor (palavras com espaço simples):
# assim um espaço duplo dentro do nome da loja continua na descrição.
LINE_RE = re.compile(
    rf"^\s*(?P<day>\d{{2}}) de (?P<month>[a-zç]{{3}})\.? (?P<year>\d{{4}})\s{{2,}}"
    rf"(?P<desc>.+)\s{{2,}}(?P<benef>\S+(?: \S+)*)\s{{2,}}(?P<credit>\+ )?R\$ (?P<value>{VALUE})\s*$"
)
DATED_RE = re.compile(r"^\s*\d{2} de [a-zç]{3}\.? \d{4}\b")
CARD_RE = re.compile(r"^\s*CARTÃO \d{4}\*{4}(?P<final>\d{4})\s*$")
TOTAL_RE = re.compile(rf"^\s*Total CARTÃO \d{{4}}\*{{4}}(?P<final>\d{{4}})\s+R\$ (?P<value>{VALUE})\s*$")
INSTALLMENT_RE = re.compile(r"\s*\(Parcela (?P<number>\d{1,2}) de (?P<total>\d{1,2})\)\s*$")
DUE_DATE_RE = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")
DUE_MARK = "Data de Vencimento"
STOP_MARK = "Próxima fatura"  # parcelas futuras, que não são desta fatura


def is_inter(text: str) -> bool:
    folded = text.casefold()
    return "banco inter" in folded and "despesas da fatura" in folded


def parse_inter(text: str) -> ParsedInvoice:
    due_date = _due_date(text)
    sections = _Sections()
    for number, line in enumerate(text.splitlines(), start=1):
        if line.strip().startswith(STOP_MARK):
            break
        sections.feed(number, line)
    return ParsedInvoice(bank="inter", due_date=due_date, cards=sections.finish())


def _due_date(text: str) -> dt.date:
    _, mark, after = text.partition(DUE_MARK)
    match = DUE_DATE_RE.search(after) if mark else None
    if match is None:
        raise invalid("file", "Não encontrei a data de vencimento da fatura.")
    day, month, year = (int(part) for part in match.groups())
    return dt.date(year, month, day)


def _cents(value: str) -> int:
    return int(value.replace(".", "").replace(",", ""))


def _brl(cents: int) -> str:
    reais, centavos = divmod(cents, 100)
    return f"R$ {reais:,}".replace(",", ".") + f",{centavos:02d}"


def _parsed_line(match: re.Match[str], position: int) -> ParsedLine:
    description = match["desc"].strip()
    installment = INSTALLMENT_RE.search(description)
    if installment:
        description = description[: installment.start()].strip()
    is_credit = match["credit"] is not None
    return ParsedLine(
        position=position,
        date=dt.date(int(match["year"]), MONTHS[match["month"]], int(match["day"])),
        description=description,
        amount_cents=_cents(match["value"]),
        is_credit=is_credit,
        # No Inter, o pagamento da fatura é um crédito "PAGAMENTO ..." (ex. "PAGAMENTO ON LINE").
        is_payment=is_credit and merchant_key(description).startswith("PAGAMENTO"),
        installment_number=int(installment["number"]) if installment else None,
        installment_total=int(installment["total"]) if installment else None,
    )


class _Sections:
    """Junta as linhas por cartão; um cabeçalho repetido (nova página) continua o mesmo bloco."""

    def __init__(self) -> None:
        self.lines: dict[str, list[ParsedLine]] = {}
        self.totals: dict[str, int] = {}
        self.current: str | None = None
        self.count = 0

    def feed(self, number: int, line: str) -> None:
        if card := CARD_RE.match(line):
            self.current = card["final"]
            self.lines.setdefault(self.current, [])
        elif total := TOTAL_RE.match(line):
            self.totals[total["final"]] = _cents(total["value"])
        elif DATED_RE.match(line):
            self._add(number, line)

    def _add(self, number: int, line: str) -> None:
        match = LINE_RE.match(line)
        try:
            if match is None or self.current is None:
                raise ValueError
            parsed = _parsed_line(match, self.count + 1)
        except (ValueError, KeyError) as error:  # sem colunas, antes de um cartão ou data impossível
            raise invalid("file", f"Não entendi a linha {number} da fatura.") from error
        self.lines[self.current].append(parsed)
        self.count += 1

    def finish(self) -> list[CardSection]:
        if self.count == 0:
            raise invalid("file", "Não encontrei lançamentos nesta fatura.")
        return [self._section(final, lines) for final, lines in self.lines.items()]

    def _section(self, final: str, lines: list[ParsedLine]) -> CardSection:
        total = self.totals.get(final)
        if total is None:
            raise invalid("file", f"Não encontrei o total do cartão final {final}.")
        # O total impresso pelo Inter soma só os débitos; pagamentos e estornos entram no "valor antecipado".
        read = sum(line.amount_cents for line in lines if not line.is_credit)
        if read != total:
            raise invalid(
                "file",
                f"A soma lida no cartão final {final} ({_brl(read)}) não confere com o total impresso "
                f"({_brl(total)}). Nada foi importado.",
            )
        return CardSection(final=final, total_cents=total, lines=lines)

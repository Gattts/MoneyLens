"""Faturas sintéticas no formato do Inter, para os testes. Nenhum dado aqui é real.

Uso no E2E: `python -m tests.invoice_samples <saída.pdf> <senha>` grava uma fatura com senha.
"""

import io
import re
import sys
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

DESCRIPTION_COLUMN = 19
BENEFICIARY_COLUMN = 80
VALUE_COLUMN = 105
LINES_PER_PAGE = 45
PAGE_WIDTH, PAGE_HEIGHT = 446, 632
SEGMENT = re.compile(r"\S+(?: \S+)*")  # trechos separados por 2 ou mais espaços


def _pad(text: str, column: int) -> str:
    return text + " " * max(2, column - len(text))


def row(date_text: str, description: str, value: str, *, credit: bool = False) -> str:
    """Uma linha de lançamento como o Inter imprime: data, descrição, beneficiário e valor."""
    text = _pad(_pad(f" {date_text}", DESCRIPTION_COLUMN) + description, BENEFICIARY_COLUMN) + "-"
    return _pad(text, VALUE_COLUMN) + (f"+ {value}" if credit else value)


def inter_text(sections: list[tuple[str, list[str], str]], *, due: str = "12/10/2026") -> str:
    """Texto de uma fatura; cada seção é (número "1111****2222", linhas de `row`, total "R$ 1,00")."""
    lines = [
        "Resumo da fatura",
        _pad("         Total da sua fatura", 60) + "Data de Vencimento",
        _pad("         R$ 0,00", 60) + due,
        "",
        "Despesas da fatura",
    ]
    for number, rows, total in sections:
        lines += ["", f" CARTÃO {number}", "", " Data          Movimentação          Beneficiário     Valor"]
        lines += rows
        lines += [_pad(f" Total CARTÃO {number}", VALUE_COLUMN) + total]
    lines += [
        "",
        "Próxima fatura",
        _pad(" GAMES *LOJA (Parcela 02 de 02)", 60) + "R$ 39,34",
        "",
        "Fale com a gente: www.bancointer.com.br · Banco Inter",
    ]
    return "\n".join(lines)


def _pdf_string(text: str) -> bytes:
    raw = text.encode("cp1252")
    return b"(" + raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)") + b")"


def _draw(lines: list[str]) -> bytes:
    ops = []
    for index, line in enumerate(lines):
        for segment in SEGMENT.finditer(line):
            x = 15 + segment.start() * 3.6
            y = PAGE_HEIGHT - 32 - index * 12
            ops.append(b"BT /F1 7 Tf %.1f %d Td %s Tj ET" % (x, y, _pdf_string(segment.group())))
    return b"\n".join(ops)


def inter_pdf(text: str, *, password: str | None = None, extra_pages: int = 0) -> bytes:
    """PDF com o texto desenhado em colunas, lido de volta pelo pypdf no modo layout."""
    writer = PdfWriter()
    font = writer._add_object(
        DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
                NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
            }
        )
    )
    lines = text.splitlines()
    for start in range(0, max(len(lines), 1), LINES_PER_PAGE):
        page = writer.add_blank_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
        )
        stream = DecodedStreamObject()
        stream.set_data(_draw(lines[start : start + LINES_PER_PAGE]))
        page[NameObject("/Contents")] = writer._add_object(stream)
    for _ in range(extra_pages):
        writer.add_blank_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    if password is not None:
        writer.encrypt(user_password=password, algorithm="AES-256")
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


UBER = row("05 de set. 2026", "UBER *TRIP", "R$ 23,90")
LOJA = row("06 de set. 2026", "LOJA NOVA", "R$ 50,00")
PAYMENT = row("07 de set. 2026", "PAGAMENTO ON LINE", "R$ 100,00", credit=True)


def invoice_pdf(
    *rows: str, total: str = "R$ 73,90", due: str = "12/10/2026", password: str | None = None
) -> bytes:
    """Fatura de um cartão só, já em PDF."""
    return inter_pdf(inter_text([("1111****2222", list(rows), total)], due=due), password=password)


def upload(client, card_id: int, pdf: bytes, **form: str):
    return client.post(
        "/api/invoice-imports",
        data={"card_id": str(card_id), **form},
        files={"file": ("fatura.pdf", pdf, "application/pdf")},
    )


E2E_INVOICE = inter_text(
    [
        (
            "1111****2222",
            [
                row("05 de set. 2026", "UBER *TRIP", "R$ 23,90"),
                row("06 de set. 2026", "LOJA DESCONHECIDA", "R$ 50,00"),
            ],
            "R$ 73,90",
        )
    ]
)

if __name__ == "__main__":
    output, password = Path(sys.argv[1]), sys.argv[2]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(inter_pdf(E2E_INVOICE, password=password))

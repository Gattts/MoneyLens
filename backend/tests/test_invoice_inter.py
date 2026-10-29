from datetime import date

import pytest

from financeiro.errors import AppError
from financeiro.services.invoices.inter import is_inter, parse_inter
from financeiro.services.invoices.pdf import read_pdf_text
from financeiro.services.invoices.reader import parse_document
from tests.invoice_samples import inter_pdf, inter_text, row

PAGE_BREAK = [
    "                                    NOME FICTICIO DA SILVA",
    "                                         9999****0000           12/10/2026   R$ 0, 00",
    "",
    "Despesas da fatura",
]


def _one_card(*rows: str, total: str) -> str:
    return inter_text([("1111****3333", list(rows), total)])


def _message(text: str) -> str:
    with pytest.raises(AppError) as error:
        parse_inter(text)
    assert error.value.field == "file"
    return error.value.message


def _line_number(text: str, line: str) -> int:
    return text.splitlines().index(line) + 1


def test_parses_lines_cards_and_due_date():
    text = inter_text(
        [
            (
                "1111****2222",
                [row("26 de ago. 2026", "PAGAMENTO ON LINE", "R$ 100,00", credit=True)],
                "R$ 0,00",
            ),
            (
                "1111****3333",
                [
                    row("23 de ago. 2026", "LOJA X", "R$ 1.046,00"),
                    row("03 de set. 2026", "GAMES *LOJA (Parcela 01 de 02)", "R$ 39,35"),
                ],
                "R$ 1.085,35",
            ),
        ]
    )
    invoice = parse_inter(text)
    assert invoice.due_date == date(2026, 10, 12)
    assert invoice.bank == "inter"
    assert [card.final for card in invoice.cards] == ["2222", "3333"]
    first, parcel = invoice.cards[1].lines
    assert (first.description, first.amount_cents, first.date) == ("LOJA X", 104600, date(2026, 8, 23))
    assert (parcel.description, parcel.installment_number, parcel.installment_total) == ("GAMES *LOJA", 1, 2)
    assert invoice.cards[0].lines[0].is_credit
    assert [line.position for line in invoice.lines] == [1, 2, 3]


@pytest.mark.parametrize(
    ("abbr", "month"),
    [
        ("jan.", 1),
        ("fev.", 2),
        ("mar.", 3),
        ("abr.", 4),
        ("mai", 5),
        ("jun.", 6),
        ("jul.", 7),
        ("ago.", 8),
        ("set.", 9),
        ("out.", 10),
        ("nov.", 11),
        ("dez.", 12),
    ],
)
def test_all_month_abbreviations(abbr, month):
    invoice = parse_inter(_one_card(row(f"05 de {abbr} 2026", "LOJA", "R$ 1,00"), total="R$ 1,00"))
    assert invoice.lines[0].date == date(2026, month, 5)


def test_description_with_double_space_stays_whole():
    invoice = parse_inter(_one_card(row("05 de set. 2026", "LOJA  CENTRO", "R$ 1,00"), total="R$ 1,00"))
    assert invoice.lines[0].description == "LOJA  CENTRO"


def test_repeated_card_header_continues_section():
    rows = [
        row("05 de set. 2026", "LOJA A", "R$ 1,00"),
        *PAGE_BREAK,
        " CARTÃO 1111****3333",
        row("06 de set. 2026", "LOJA B", "R$ 2,00"),
    ]
    invoice = parse_inter(_one_card(*rows, total="R$ 3,00"))
    assert len(invoice.cards) == 1
    assert [line.description for line in invoice.cards[0].lines] == ["LOJA A", "LOJA B"]


def test_page_header_lines_are_ignored():
    rows = [row("05 de set. 2026", "LOJA A", "R$ 1,00"), *PAGE_BREAK]
    assert len(parse_inter(_one_card(*rows, total="R$ 1,00")).lines) == 1


def test_credits_do_not_count_in_card_total():
    rows = [
        row("05 de set. 2026", "LOJA", "R$ 10,00"),
        row("06 de set. 2026", "LOJA", "R$ 5,00", credit=True),
    ]
    assert parse_inter(_one_card(*rows, total="R$ 10,00")).cards[0].total_cents == 1000


def test_sum_mismatch_names_card_and_values():
    text = _one_card(row("05 de set. 2026", "LOJA", "R$ 10,00"), total="R$ 1.012,00")
    assert _message(text) == (
        "A soma lida no cartão final 3333 (R$ 10,00) não confere com o total impresso (R$ 1.012,00). "
        "Nada foi importado."
    )


def test_unreadable_dated_line_reports_line_number():
    broken = " 05 de set. 2026   SEM VALOR"
    text = _one_card(row("04 de set. 2026", "LOJA", "R$ 1,00"), broken, total="R$ 1,00")
    assert _message(text) == f"Não entendi a linha {_line_number(text, broken)} da fatura."


def test_impossible_date_is_an_unreadable_line():
    broken = row("31 de fev. 2026", "LOJA", "R$ 1,00")
    text = _one_card(broken, total="R$ 1,00")
    assert _message(text) == f"Não entendi a linha {_line_number(text, broken)} da fatura."


def test_missing_due_date():
    text = _one_card(row("05 de set. 2026", "LOJA", "R$ 1,00"), total="R$ 1,00")
    assert _message(text.replace("Data de Vencimento", "Vencimento")) == (
        "Não encontrei a data de vencimento da fatura."
    )


def test_line_before_card_header_is_an_error():
    early = row("01 de set. 2026", "ANTES DO CARTAO", "R$ 1,00")
    text = _one_card(row("05 de set. 2026", "LOJA", "R$ 1,00"), total="R$ 1,00")
    text = text.replace("Despesas da fatura", f"Despesas da fatura\n{early}")
    assert _message(text) == f"Não entendi a linha {_line_number(text, early)} da fatura."


def test_card_without_total():
    text = _one_card(row("05 de set. 2026", "LOJA", "R$ 1,00"), total="R$ 1,00")
    text = "\n".join(line for line in text.splitlines() if "Total CARTÃO" not in line)
    assert _message(text) == "Não encontrei o total do cartão final 3333."


def test_invoice_without_lines():
    assert _message(inter_text([])) == "Não encontrei lançamentos nesta fatura."


def test_next_invoice_section_is_ignored():
    text = _one_card(row("05 de set. 2026", "LOJA", "R$ 1,00"), total="R$ 1,00")
    text = text.replace("Próxima fatura", f"Próxima fatura\n{row('05 de nov. 2026', 'FUTURA', 'R$ 9,99')}")
    assert [line.description for line in parse_inter(text).lines] == ["LOJA"]


def test_reads_synthetic_pdf_end_to_end():
    text = _one_card(
        row("05 de set. 2026", "UBER *TRIP", "R$ 23,90"),
        row("06 de set. 2026", "PAGAMENTO ON LINE", "R$ 23,90", credit=True),
        total="R$ 23,90",
    )
    extracted = read_pdf_text(inter_pdf(text, password="4321"), password="4321", saved_password=None).text
    assert [(line.description, line.is_credit, line.is_payment) for line in parse_inter(extracted).lines] == [
        ("UBER *TRIP", False, False),
        ("PAGAMENTO ON LINE", True, True),
    ]


def test_is_inter_requires_both_marks():
    assert is_inter(_one_card(row("05 de set. 2026", "LOJA", "R$ 1,00"), total="R$ 1,00"))
    assert not is_inter("Fatura do Banco Inter")


def test_parse_document_dispatches_and_rejects_other_banks():
    text = _one_card(row("05 de set. 2026", "LOJA", "R$ 1,00"), total="R$ 1,00")
    assert parse_document(text).bank == "inter"
    with pytest.raises(AppError) as error:
        parse_document("Fatura do Banco Qualquer")
    assert (error.value.field, error.value.message) == (
        "file",
        "Ainda não sei ler este arquivo. Por enquanto: fatura do Inter e extratos do Nubank e do PicPay.",
    )

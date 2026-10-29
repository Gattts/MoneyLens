from datetime import date

import pytest

from financeiro.domain.enums import ImportSource, PaymentMethod
from financeiro.domain.invoices import ParsedInvoice
from financeiro.domain.statements import ParsedStatement, StatementNature
from financeiro.errors import AppError
from financeiro.services.invoices.nubank import is_nubank_statement, parse_nubank
from financeiro.services.invoices.pdf import read_pdf_text
from financeiro.services.invoices.reader import parse_as, parse_document
from tests.invoice_samples import inter_text, row
from tests.statement_samples import (
    APPLY,
    CARD_PAYMENT,
    DEBIT,
    PIX_OUT,
    REDEEM,
    TRANSFER_IN,
    Day,
    Entry,
    pix_in,
    pix_out,
    statement_pages,
    statement_pdf,
    statement_text,
)

OUTFLOW, INFLOW = StatementNature.OUTFLOW, StatementNature.INFLOW
INVESTMENT, OWN = StatementNature.INVESTMENT, StatementNature.OWN_TRANSFER
PIX, TRANSFER = PaymentMethod.PIX, PaymentMethod.TRANSFER
MISMATCH = "Não consegui conferir o extrato: os totais não batem. Nada foi importado."
TWO_OUT = [Day("05 OUT 2026", outflows=[pix_out("LOJA UM", "10,00"), pix_out("LOJA DOIS", "20,00")])]


def _from_pdf(pages: list[str]) -> str:
    return read_pdf_text(statement_pdf(pages), password=None, saved_password=None).text


def _summary(parsed: ParsedStatement) -> list[tuple]:
    return [(line.description, line.is_credit, line.amount_cents) for line in parsed.lines]


def test_reads_days_blocks_and_signs():
    days = [
        Day("01 OUT 2026", outflows=[pix_out("LANCHONETE ALFA", "37,15")]),
        Day(
            "02 OUT 2026",
            inflows=[Entry(REDEEM, "", "27,00"), pix_in("EMPRESA X", "1.500,00")],
            outflows=[pix_out("PADARIA", "10,00")],
        ),
    ]
    parsed = parse_nubank(_from_pdf(statement_pages(days)))
    assert (parsed.bank, parsed.holder, parsed.period_start, parsed.period_end) == (
        "nubank",
        "ANA SOUZA",
        date(2026, 10, 1),
        date(2026, 10, 27),
    )
    assert [
        (line.position, line.date, line.nature, line.is_credit, line.description, line.amount_cents)
        for line in parsed.lines
    ] == [
        (1, date(2026, 10, 1), OUTFLOW, False, "LANCHONETE ALFA", 3715),
        (2, date(2026, 10, 2), INVESTMENT, True, "Resgate RDB", 2700),
        (3, date(2026, 10, 2), INFLOW, True, "EMPRESA X", 150000),
        (4, date(2026, 10, 2), OUTFLOW, False, "PADARIA", 1000),
    ]
    assert [line.payment_method for line in parsed.lines] == [PIX, TRANSFER, PIX, PIX]


def test_description_spans_lines_and_pages():
    entry = Entry(
        PIX_OUT, "LOJA X", "7,00", ["- 12.345.678/0001-90 - BANCO EXEMPLO S.A.", "(0999) Agência: 1"]
    )
    pages = statement_pages([Day("03 OUT 2026", outflows=[entry])], break_after=3)
    assert len(pages) == 2
    parsed = parse_nubank(_from_pdf(pages))
    assert [(line.counterparty, line.description, line.amount_cents) for line in parsed.lines] == [
        ("LOJA X", "LOJA X", 700)
    ]


def test_block_continues_on_next_page():
    pages = statement_pages(TWO_OUT, break_after=6)
    assert "LOJA DOIS" in pages[1] and "Total de saídas" not in pages[1].split("VALORES EM R$")[1]
    parsed = parse_nubank(_from_pdf(pages))
    assert _summary(parsed) == [("LOJA UM", False, 1000), ("LOJA DOIS", False, 2000)]


def test_thousands_and_signs_in_summary():
    days = [
        Day("10 OUT 2026", inflows=[pix_in("EMPRESA X", "2.468,13")], outflows=[pix_out("LOJA", "2.391,77")])
    ]
    parsed = parse_nubank(_from_pdf(statement_pages(days, opening="-15,20")))
    assert _summary(parsed) == [("EMPRESA X", True, 246813), ("LOJA", False, 239177)]


def test_counterparty_strips_documents_and_bank():
    days = [
        Day(
            "04 OUT 2026",
            outflows=[
                Entry(
                    PIX_OUT,
                    "LANCHONETE ALFA - 60.000.000/0001-00 - BANCO X",
                    "1,00",
                    ["S.A. (0999) Agência: 7 Conta: 1-", "0"],
                ),
                pix_out("MARIA SILVA", "2,00", "•••.000.111-••"),
                pix_out("LOJA X - FILIAL CENTRO", "3,00"),
                Entry(PIX_OUT, "SEM DOCUMENTO", "4,00"),
            ],
        )
    ]
    parsed = parse_nubank(statement_text(days))
    assert [line.counterparty for line in parsed.lines] == [
        "LANCHONETE ALFA",
        "MARIA SILVA",
        "LOJA X - FILIAL CENTRO",
        "SEM DOCUMENTO",
    ]


def test_own_transfer_only_on_exact_holder_name():
    days = [
        Day(
            "06 OUT 2026",
            inflows=[pix_in("ANA SOUZA JUNIOR", "5,00")],
            outflows=[pix_out("Ána  Souza", "8,00", "•••.123.456-••")],
        )
    ]
    parsed = parse_nubank(statement_text(days))
    assert [(line.description, line.nature) for line in parsed.lines] == [
        ("ANA SOUZA JUNIOR", INFLOW),
        ("Ána Souza", OWN),
    ]


def test_types_map_to_natures():
    days = [
        Day(
            "07 OUT 2026",
            inflows=[
                Entry(REDEEM, "", "1,00"),
                Entry(TRANSFER_IN, "JOAO LIMA - •••.111.222-••", "2,00"),
                Entry("Estorno de compra", "LOJA Z", "3,00"),
            ],
            outflows=[
                Entry(APPLY, "", "4,00"),
                Entry(CARD_PAYMENT, "", "5,00"),
                Entry(DEBIT, "MERCADO BOM", "6,00"),
            ],
        )
    ]
    parsed = parse_nubank(statement_text(days))
    assert [
        (line.description, line.nature, line.is_credit, line.payment_method) for line in parsed.lines
    ] == [
        ("Resgate RDB", INVESTMENT, True, TRANSFER),
        ("JOAO LIMA", INFLOW, True, TRANSFER),
        ("Estorno de compra LOJA Z", INFLOW, True, TRANSFER),
        ("Aplicação RDB", INVESTMENT, False, TRANSFER),
        ("Pagamento de fatura", StatementNature.CARD_PAYMENT, False, TRANSFER),
        ("MERCADO BOM", OUTFLOW, False, PaymentMethod.DEBIT),
    ]


@pytest.mark.parametrize(
    "text",
    [
        statement_text(TWO_OUT).replace("- 30,00", "- 31,00"),  # total do bloco
        statement_text(TWO_OUT, expense="31,00"),
        statement_text(TWO_OUT, income="1,00"),
        statement_text(TWO_OUT, closing="70,01"),
    ],
    ids=["bloco", "saídas", "entradas", "saldo final"],
)
def test_mismatched_totals_refuse_the_file(text):
    with pytest.raises(AppError) as error:
        parse_nubank(text)
    assert (error.value.field, error.value.message) == ("file", MISMATCH)


def test_yield_may_explain_the_closing_balance():
    parsed = parse_nubank(statement_text(TWO_OUT, yield_="+0,50", closing="70,50"))
    assert len(parsed.lines) == 2


def test_empty_statement_is_accepted():
    assert parse_nubank(statement_text([])).lines == []


def test_reader_picks_nubank_or_inter():
    statement = statement_text(TWO_OUT)
    invoice = inter_text([("1111****2222", [row("05 de set. 2026", "LOJA", "R$ 1,00")], "R$ 1,00")])
    assert is_nubank_statement(statement) and not is_nubank_statement(invoice)
    assert isinstance(parse_document(statement), ParsedStatement)
    assert isinstance(parse_document(invoice), ParsedInvoice)
    with pytest.raises(AppError) as unknown:
        parse_document("Extrato do Banco Qualquer")
    assert unknown.value.message == (
        "Ainda não sei ler este arquivo. Por enquanto: fatura do Inter e extratos do Nubank e do PicPay."
    )
    with pytest.raises(AppError) as swapped:
        parse_as(statement, ImportSource.CARD_INVOICE)
    assert swapped.value.message == "Este arquivo é um extrato de conta. Escolha Extrato da conta."
    with pytest.raises(AppError) as swapped_back:
        parse_as(invoice, ImportSource.ACCOUNT_STATEMENT)
    assert (
        swapped_back.value.message
        == "Este arquivo é uma fatura de cartão. Escolha Fatura do cartão e o cartão."
    )

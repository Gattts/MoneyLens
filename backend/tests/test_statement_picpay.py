from datetime import date

import pytest

from financeiro.domain.banks import bank_name
from financeiro.domain.enums import ImportSource, PaymentMethod
from financeiro.domain.statements import ParsedStatement, StatementNature
from financeiro.errors import AppError
from financeiro.services.invoices.nubank import is_nubank_statement
from financeiro.services.invoices.pdf import read_pdf_text
from financeiro.services.invoices.picpay import is_picpay_statement, parse_picpay
from financeiro.services.invoices.reader import parse_as, parse_document
from tests.invoice_samples import inter_text, row
from tests.picpay_samples import (
    BALANCE,
    CARD,
    CARD_INVOICE,
    MIXED,
    PAYMENT,
    PIX_IN,
    PIX_OUT,
    PURCHASE,
    REDEEMED,
    REFUND,
    SAVED,
    Day,
    Entry,
    received,
    spent,
    statement_pages,
    statement_pdf,
    statement_text,
)
from tests.statement_samples import statement_text as nubank_text
from tests.statement_samples import upload_statement

OUTFLOW, INFLOW = StatementNature.OUTFLOW, StatementNature.INFLOW
INVESTMENT, OWN = StatementNature.INVESTMENT, StatementNature.OWN_TRANSFER
PIX, TRANSFER, DEBIT = PaymentMethod.PIX, PaymentMethod.TRANSFER, PaymentMethod.DEBIT
MISMATCH = "Não consegui conferir o extrato: os saldos não batem. Nada foi importado."
DAYS = [
    Day(
        "3 de outubro 2026",
        [
            spent(PAYMENT, CARD_INVOICE, "40,00", time="18:00"),
            spent(PAYMENT, "Seguro de Vida", "13,80", time="17:00"),
            received(REFUND, "LOJA ONLINE", "15,00", time="16:00"),
            spent(PURCHASE, "LOJA ONLINE", "15,00", time="15:59"),
        ],
    ),
    Day(
        "2 de outubro 2026",
        [
            received(REDEEMED, "Do cofrinho viagem", "20,00", time="11:00"),
            spent(SAVED, "No cofrinho viagem", "50,00", time="10:00"),
            received(PIX_IN, "EMPRESA X", "1.500,00", time="09:00"),
        ],
    ),
    Day("1 de outubro 2026", [spent(PIX_OUT, "LANCHONETE ALFA", "37,15", time="08:00")]),
]
SIMPLE = [
    Day("5 de outubro 2026", [spent(PIX_OUT, "LOJA", "10,00")]),
    Day("4 de outubro 2026", [received(PIX_IN, "EMPRESA", "50,00")]),
]


def _from_pdf(pages: list[str]) -> str:
    return read_pdf_text(statement_pdf(pages), password=None, saved_password=None).text


def _summary(parsed: ParsedStatement) -> list[tuple]:
    return [(line.description, line.is_credit, line.amount_cents) for line in parsed.lines]


def test_reads_days_types_and_signs_oldest_first():
    parsed = parse_picpay(_from_pdf(statement_pages(DAYS, opening="100,00")))
    assert (parsed.bank, parsed.holder, parsed.period_start, parsed.period_end) == (
        "picpay",
        "ANA SOUZA",
        date(2026, 10, 1),
        date(2026, 10, 27),
    )
    assert [
        (line.position, line.date, line.nature, line.is_credit, line.description, line.amount_cents)
        for line in parsed.lines
    ] == [
        (1, date(2026, 10, 1), OUTFLOW, False, "LANCHONETE ALFA", 3715),
        (2, date(2026, 10, 2), INFLOW, True, "EMPRESA X", 150000),
        (3, date(2026, 10, 2), INVESTMENT, False, "Dinheiro guardado", 5000),
        (4, date(2026, 10, 2), INVESTMENT, True, "Dinheiro resgatado", 2000),
        (5, date(2026, 10, 3), OUTFLOW, False, "LOJA ONLINE", 1500),
        (6, date(2026, 10, 3), INFLOW, True, "Estorno LOJA ONLINE", 1500),
        (7, date(2026, 10, 3), OUTFLOW, False, "Seguro de Vida", 1380),
        (8, date(2026, 10, 3), StatementNature.CARD_PAYMENT, False, "Fatura PicPay Card", 4000),
    ]
    assert [line.payment_method for line in parsed.lines] == [
        PIX, PIX, TRANSFER, TRANSFER, DEBIT, DEBIT, DEBIT, TRANSFER
    ]  # fmt: skip
    assert [line.counterparty for line in parsed.lines][:3] == ["LANCHONETE ALFA", "EMPRESA X", ""]


def test_card_purchases_stay_for_the_invoice_and_mixed_keeps_the_balance_part():
    days = [
        Day(
            "5 de outubro 2026",
            [
                spent(PURCHASE, "TRANSPORTE APP", "30,00", MIXED, time="10:00", from_balance=1200),
                spent(PAYMENT, "Seguro Celular", "11,35", CARD, time="09:00"),
                spent(PURCHASE, "LOJA DE APPS", "27,60", CARD, time="08:00"),
            ],
        ),
        Day("4 de outubro 2026", [received(PIX_IN, "JOAO PRADO", "12,00")]),
    ]
    parsed = parse_picpay(_from_pdf(statement_pages(days)))
    assert _summary(parsed) == [("JOAO PRADO", True, 1200), ("TRANSPORTE APP", False, 1200)]
    assert parsed.lines[-1].payment_method is DEBIT


def test_several_mixed_purchases_share_the_day_difference_from_the_oldest():
    days = [
        Day(
            "6 de outubro 2026",
            [
                spent(PURCHASE, "TRANSPORTE APP", "18,40", MIXED, time="16:47", from_balance=1200),
                received(REFUND, "TRANSPORTE APP", "22,37", time="16:36"),
                spent(PURCHASE, "TRANSPORTE APP", "22,37", MIXED, time="16:36", from_balance=2237),
            ],
        ),
        Day("5 de outubro 2026", [received(PIX_IN, "EMPRESA", "50,00")]),
    ]
    parsed = parse_picpay(statement_text(days))
    assert _summary(parsed) == [
        ("EMPRESA", True, 5000),
        ("TRANSPORTE APP", False, 2237),
        ("Estorno TRANSPORTE APP", True, 2237),
        ("TRANSPORTE APP", False, 1200),
    ]


def test_mixed_purchase_paid_all_by_card_is_left_out():
    days = [
        Day("6 de outubro 2026", [spent(PURCHASE, "TRANSPORTE APP", "18,40", MIXED, from_balance=0)]),
        Day("5 de outubro 2026", [spent(PIX_OUT, "LOJA", "10,00")]),
    ]
    parsed = parse_picpay(statement_text(days, opening="10,00"))
    assert _summary(parsed) == [("LOJA", False, 1000)]


def test_mixed_purchase_on_the_oldest_day_counts_in_full():
    # O primeiro dia não tem saldo anterior impresso: não há como saber a parte do saldo.
    days = [Day("4 de outubro 2026", [spent(PURCHASE, "TRANSPORTE APP", "30,00", MIXED, from_balance=1000)])]
    parsed = parse_picpay(statement_text(days, opening="10,00"))
    assert _summary(parsed) == [("TRANSPORTE APP", False, 3000)]


def test_day_continues_on_the_next_page_and_names_wrap():
    days = [
        Day(
            "7 de outubro 2026",
            [
                spent(PIX_OUT, "CARLA MENDES", "5,00", extra=["TAVARES"], time="10:00"),
                spent(PIX_OUT, "LOJA X", "7,00", time="09:00"),
            ],
        ),
        Day("6 de outubro 2026", [received(PIX_IN, "EMPRESA", "50,00")]),
    ]
    pages = statement_pages(days, break_after=1)
    assert len(pages) == 2 and "7 de outubro 2026" in pages[1]
    parsed = parse_picpay(_from_pdf(pages))
    assert _summary(parsed) == [
        ("EMPRESA", True, 5000),
        ("LOJA X", False, 700),
        ("CARLA MENDES TAVARES", False, 500),
    ]


def test_own_transfer_and_mei_prefix():
    days = [
        Day(
            "8 de outubro 2026",
            [
                spent(PIX_OUT, "ANA", "8,00", extra=["SOUZA"]),
                spent(PIX_OUT, "12.345.678 JOSE PRADO", "3,00"),
                received(PIX_IN, "ANA SOUZA JUNIOR", "50,00"),
            ],
        )
    ]
    parsed = parse_picpay(_from_pdf(statement_pages(days, holder="Ana Souza")))
    assert [(line.counterparty, line.description, line.nature) for line in parsed.lines] == [
        ("ANA SOUZA JUNIOR", "ANA SOUZA JUNIOR", INFLOW),
        ("JOSE PRADO", "JOSE PRADO", OUTFLOW),
        ("ANA SOUZA", "ANA SOUZA", OWN),
    ]


def test_unknown_types_keep_the_printed_text():
    days = [
        Day(
            "9 de outubro 2026",
            [Entry("Seguro Carteira Digital", "", -745, BALANCE), Entry("Tarifa", "PACOTE X", -100, BALANCE)],
        )
    ]
    parsed = parse_picpay(_from_pdf(statement_pages(days, opening="20,00")))
    assert [(line.description, line.nature, line.payment_method) for line in parsed.lines] == [
        ("Tarifa PACOTE X", OUTFLOW, TRANSFER),
        ("Seguro Carteira Digital", OUTFLOW, TRANSFER),
    ]


def test_negative_balances_and_thousands():
    days = [
        Day(
            "4 de outubro 2026",
            [spent(PIX_OUT, "LOJA", "2.500,00"), received(PIX_IN, "EMPRESA X", "2.468,13")],
        )
    ]
    parsed = parse_picpay(_from_pdf(statement_pages(days, opening="-50,00")))
    assert _summary(parsed) == [("EMPRESA X", True, 246813), ("LOJA", False, 250000)]


@pytest.mark.parametrize(
    "text",
    [
        statement_text(SIMPLE, closings={"5 de outubro 2026": "41,00"}),
        statement_text(SIMPLE, final="39,00"),
        statement_text(
            [
                Day(
                    "5 de outubro 2026",
                    [spent(PURCHASE, "TRANSPORTE APP", "10,00", MIXED, from_balance=1500)],
                ),
                SIMPLE[1],
            ]
        ),
        statement_text(
            [
                Day(
                    "5 de outubro 2026",
                    [spent(PURCHASE, "TRANSPORTE APP", "10,00", MIXED, from_balance=-100)],
                ),
                SIMPLE[1],
            ]
        ),
        statement_text(SIMPLE[::-1]),
    ],
    ids=["saldo do dia", "saldo final", "misto acima do valor", "misto negativo", "dias fora de ordem"],
)
def test_mismatched_balances_refuse_the_file(text):
    with pytest.raises(AppError) as error:
        parse_picpay(text)
    assert (error.value.field, error.value.message) == ("file", MISMATCH)


def test_empty_statement_is_accepted():
    parsed = parse_picpay(statement_text([], opening="3,00"))
    assert (parsed.lines, parsed.period_start) == ([], date(2026, 10, 1))


def test_reader_picks_picpay():
    picpay = statement_text(SIMPLE)
    nubank = nubank_text([])
    invoice = inter_text([("1111****2222", [row("05 de set. 2026", "LOJA", "R$ 1,00")], "R$ 1,00")])
    assert is_picpay_statement(picpay)
    assert not is_picpay_statement(nubank) and not is_picpay_statement(invoice)
    assert not is_nubank_statement(picpay)
    assert parse_document(picpay).bank == "picpay"
    with pytest.raises(AppError) as unknown:
        parse_document("Extrato do Banco Qualquer")
    assert unknown.value.message == (
        "Ainda não sei ler este arquivo. Por enquanto: fatura do Inter e extratos do Nubank e do PicPay."
    )
    with pytest.raises(AppError) as swapped:
        parse_as(picpay, ImportSource.CARD_INVOICE)
    assert swapped.value.message == "Este arquivo é um extrato de conta. Escolha Extrato da conta."
    assert bank_name("picpay") == "PicPay"


def test_upload_picpay_statement(client):
    days = [
        Day(
            "3 de outubro 2026",
            [
                spent(PAYMENT, CARD_INVOICE, "40,00", time="18:00"),
                spent(PURCHASE, "LOJA DE APPS", "27,60", CARD, time="17:00"),
                spent(PIX_OUT, "ANA SOUZA", "10,00", time="16:00"),
                spent(SAVED, "No cofrinho viagem", "50,00", time="10:00"),
                received(PIX_IN, "EMPRESA X", "1.500,00", time="09:00"),
            ],
        )
    ]
    response = upload_statement(client, statement_pdf(statement_pages(days)))
    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["source"], body["bank"]) == ("account_statement", "picpay")
    assert [
        (line["description"], line["kind"], line["payment_method"], line["status"], line["skip_reason"])
        for line in body["lines"]
    ] == [
        ("EMPRESA X", "income", "pix", "pending", None),
        ("Dinheiro guardado", "expense", "transfer", "skipped", "investment"),
        ("ANA SOUZA", "expense", "pix", "skipped", "own_transfer"),
        ("Fatura PicPay Card", "expense", "transfer", "skipped", "card_payment"),
        ("Dinheiro guardado no período", "expense", "transfer", "pending", None),
    ]

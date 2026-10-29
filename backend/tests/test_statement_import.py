from datetime import date

import pytest
from sqlalchemy import select

from financeiro.domain.enums import ImportSource, LineStatus, PaymentMethod, SkipReason
from financeiro.domain.statements import ParsedStatement, ParsedStatementLine
from financeiro.domain.statements import StatementNature as N
from financeiro.models import InvoiceImport, InvoiceLine
from financeiro.services.invoices.statement_importer import SAVED_KEY, import_statement
from tests.factories import (
    create_card,
    create_category,
    create_income_category,
    create_recurring,
    create_transaction,
    create_transactions,
)

START, END = date(2026, 10, 1), date(2026, 10, 27)
PIX, TRANSFER = PaymentMethod.PIX, PaymentMethod.TRANSFER
IDENTIFIED, PENDING, SKIPPED = LineStatus.IDENTIFIED, LineStatus.PENDING, LineStatus.SKIPPED


def _line(position: int, description: str, cents: int, *, nature: N = N.OUTFLOW, day: int = 5, credit=None):
    is_credit = (nature is N.INFLOW) if credit is None else credit
    method = TRANSFER if nature in (N.INVESTMENT, N.CARD_PAYMENT) else PIX
    return ParsedStatementLine(
        position, date(2026, 10, day), nature, is_credit, description, description, cents, method
    )


def _apply(position: int, cents: int, day: int = 3):
    return _line(position, "Aplicação RDB", cents, nature=N.INVESTMENT, credit=False, day=day)


def _redeem(position: int, cents: int, day: int = 4):
    return _line(position, "Resgate RDB", cents, nature=N.INVESTMENT, credit=True, day=day)


def _statement(*lines: ParsedStatementLine, start: date = START, end: date = END) -> ParsedStatement:
    return ParsedStatement("nubank", "ANA SOUZA", start, end, list(lines))


def _rows(db, statement: InvoiceImport) -> list[InvoiceLine]:
    query = select(InvoiceLine).where(InvoiceLine.import_id == statement.id).order_by(InvoiceLine.position)
    return list(db.scalars(query).all())


def _states(db, statement: InvoiceImport) -> list[tuple]:
    return [(row.description, row.status, row.skip_reason) for row in _rows(db, statement)]


def _rule(client, pattern: str, category_id: int) -> None:
    rule = {"pattern": pattern, "match_type": "contains", "category_id": category_id}
    assert client.post("/api/category-rules", json=rule).status_code == 201


def test_lines_are_classified_by_nature_and_rules(client, db, user):
    food = create_category(client, name="Comida fora", default_bucket="wants")
    _rule(client, "99FOOD", food["id"])
    statement, created = import_statement(
        db,
        user.id,
        _statement(
            _line(1, "99 FOOD", 3715),
            _line(2, "PADARIA", 1000),
            _line(3, "Pagamento de fatura", 50000, nature=N.CARD_PAYMENT, credit=False),
            _line(4, "ANA SOUZA", 2000, nature=N.OWN_TRANSFER, credit=True),
            _redeem(5, 2700),
        ),
    )
    assert created
    assert (statement.source, statement.card_id, statement.due_date) == (
        ImportSource.ACCOUNT_STATEMENT,
        None,
        None,
    )
    assert (statement.bank, statement.period_start, statement.period_end) == ("nubank", START, END)
    assert statement.total_cents == 3715 + 1000 + 50000
    assert _states(db, statement) == [
        ("99 FOOD", IDENTIFIED, None),
        ("PADARIA", PENDING, None),
        ("Pagamento de fatura", SKIPPED, SkipReason.CARD_PAYMENT),
        ("ANA SOUZA", SKIPPED, SkipReason.OWN_TRANSFER),
        ("Resgate RDB", SKIPPED, SkipReason.INVESTMENT),
    ]
    first = _rows(db, statement)[0]
    assert (first.category_id, first.payment_method, first.merchant_key) == (food["id"], PIX, "99 FOOD")


def test_income_line_uses_income_rule(client, db, user):
    salary = create_income_category(client)
    gifts = create_category(client, name="Presentes", default_bucket="wants")
    _rule(client, "EMPRESA X", salary["id"])
    _rule(client, "EMPRESA X", gifts["id"])
    statement, _ = import_statement(
        db, user.id, _statement(_line(1, "EMPRESA X", 150000, nature=N.INFLOW), _line(2, "EMPRESA X", 1000))
    )
    assert [(row.status, row.category_id) for row in _rows(db, statement)] == [
        (IDENTIFIED, salary["id"]),
        (IDENTIFIED, gifts["id"]),
    ]


def test_overlapping_statement_skips_already_imported(db, user):
    import_statement(
        db,
        user.id,
        _statement(_line(1, "PADARIA", 1000), _line(2, "LOJA", 2000, day=6), end=date(2026, 10, 15)),
    )
    second, created = import_statement(
        db,
        user.id,
        _statement(
            _line(1, "PADARIA", 1000),
            _line(2, "LOJA", 2000, day=6, nature=N.INFLOW),  # mesmo valor e dia, outro sentido
            _line(3, "MERCADO", 3000, day=20),
            start=date(2026, 10, 5),
            end=date(2026, 10, 31),
        ),
    )
    assert created
    assert _states(db, second) == [
        ("PADARIA", SKIPPED, SkipReason.ALREADY_IMPORTED),
        ("LOJA", PENDING, None),
        ("MERCADO", PENDING, None),
    ]


def test_identical_lines_count_occurrences(db, user):
    import_statement(db, user.id, _statement(_line(1, "UBER", 2390, day=7), end=date(2026, 10, 10)))
    second, _ = import_statement(
        db, user.id, _statement(_line(1, "UBER", 2390, day=7), _line(2, "UBER", 2390, day=7))
    )
    assert [row.skip_reason for row in _rows(db, second)] == [SkipReason.ALREADY_IMPORTED, None]


def test_echo_lines_are_not_proof_after_an_undo(db, user):
    """A linha que o extrato B só repetiu de A não prova nada quando A é desfeito e lido de novo."""
    first, _ = import_statement(db, user.id, _statement(_line(1, "PADARIA", 1000), end=date(2026, 10, 15)))
    second, _ = import_statement(db, user.id, _statement(_line(1, "PADARIA", 1000), start=date(2026, 10, 2)))
    assert _states(db, second) == [("PADARIA", SKIPPED, SkipReason.ALREADY_IMPORTED)]
    db.delete(first)
    db.commit()
    again, created = import_statement(
        db, user.id, _statement(_line(1, "PADARIA", 1000), end=date(2026, 10, 15))
    )
    assert created
    assert _states(db, again) == [("PADARIA", PENDING, None)]


def test_echo_lines_do_not_add_up_across_overlapping_statements(db, user):
    """Duas corridas iguais no dia: A e B viram só a primeira; C traz as duas e a segunda não pode sumir."""
    import_statement(db, user.id, _statement(_line(1, "UBER", 2390), end=date(2026, 10, 5)))
    import_statement(
        db, user.id, _statement(_line(1, "UBER", 2390), start=date(2026, 10, 3), end=date(2026, 10, 5))
    )
    third, _ = import_statement(
        db,
        user.id,
        _statement(
            _line(1, "UBER", 2390), _line(2, "UBER", 2390), start=date(2026, 10, 4), end=date(2026, 10, 31)
        ),
    )
    assert [row.skip_reason for row in _rows(db, third)] == [SkipReason.ALREADY_IMPORTED, None]


def test_saved_money_line_from_new_investments(client, db, user):
    savings = create_category(client, name="Investimentos", default_bucket="savings")
    _rule(client, "DINHEIRO GUARDADO", savings["id"])
    statement, _ = import_statement(
        db, user.id, _statement(_apply(1, 90000), _apply(2, 15000), _redeem(3, 2700))
    )
    saved = _rows(db, statement)[-1]
    assert (saved.position, saved.description, saved.merchant_key) == (
        4,
        "Dinheiro guardado no período",
        SAVED_KEY,
    )
    assert (saved.amount_cents, saved.date, saved.is_credit, saved.payment_method) == (
        102300,
        END,
        False,
        TRANSFER,
    )
    assert (saved.status, saved.category_id) == (IDENTIFIED, savings["id"])


@pytest.mark.parametrize(("applied", "redeemed"), [(10000, 10000), (5000, 9000)])
def test_no_saved_money_line_when_net_not_positive(db, user, applied, redeemed):
    statement, _ = import_statement(db, user.id, _statement(_apply(1, applied), _redeem(2, redeemed)))
    assert [row.merchant_key for row in _rows(db, statement)] == ["APLICACAO RDB", "RESGATE RDB"]


def test_saved_money_ignores_already_imported_investments(db, user):
    import_statement(db, user.id, _statement(_apply(1, 50000), end=date(2026, 10, 15)))
    second, _ = import_statement(db, user.id, _statement(_apply(1, 50000), _apply(2, 15000, day=20)))
    saved = _rows(db, second)[-1]
    assert (saved.merchant_key, saved.amount_cents) == (SAVED_KEY, 15000)


def test_manual_entry_is_possible_duplicate(client, db, user):
    category = create_category(client)
    create_transaction(client, category["id"], amount_cents=1250, date="2026-10-07")
    statement, _ = import_statement(
        db, user.id, _statement(_line(1, "PADARIA", 1250, day=5), _line(2, "PADARIA", 1250, day=11))
    )
    assert [(row.status, row.skip_reason) for row in _rows(db, statement)] == [
        (SKIPPED, SkipReason.DUPLICATE),
        (PENDING, None),
    ]


def test_pix_installment_launched_by_hand_is_a_possible_duplicate(client, db, user):
    """Pix parcelado lançado à mão em 3x: a parcela de outubro que aparece no extrato não conta duas vezes."""
    category = create_category(client)
    create_transactions(
        client, category["id"], amount_cents=30000, date="2026-09-05", payment_method="pix", installments=3
    )
    statement, _ = import_statement(db, user.id, _statement(_line(1, "LOJA PARCELADA", 10000, day=6)))
    assert [row.skip_reason for row in _rows(db, statement)] == [SkipReason.DUPLICATE]


def test_card_purchase_is_not_a_duplicate_of_pix(client, db, user):
    category = create_category(client)
    card = create_card(client)
    create_transaction(
        client,
        category["id"],
        amount_cents=1250,
        date="2026-10-05",
        payment_method="credit_card",
        card_id=card["id"],
    )
    statement, _ = import_statement(db, user.id, _statement(_line(1, "PADARIA", 1250)))
    assert _states(db, statement) == [("PADARIA", PENDING, None)]


def test_pending_recurring_is_possible_duplicate(client, db, user):
    salary = create_income_category(client)
    create_recurring(
        client,
        salary["id"],
        description="Salário",
        kind="income",
        amount_cents=500000,
        day_of_month=5,
        payment_method="transfer",
    )
    statement, _ = import_statement(
        db,
        user.id,
        _statement(_line(1, "EMPRESA X", 500000, nature=N.INFLOW, day=6), _line(2, "LOJA", 500000, day=6)),
    )
    assert [row.skip_reason for row in _rows(db, statement)] == [SkipReason.DUPLICATE, None]


def test_same_statement_twice_returns_existing(db, user):
    first, created = import_statement(db, user.id, _statement(_line(1, "PADARIA", 1000)))
    again, created_again = import_statement(db, user.id, _statement(_line(1, "PADARIA", 1000)))
    assert (created, created_again, again.id) == (True, False, first.id)
    assert len(_rows(db, first)) == 1

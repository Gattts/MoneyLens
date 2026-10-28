import pytest

from tests.factories import (
    create_category,
    create_income_category,
    create_recurring,
    create_transaction,
)


@pytest.fixture
def october(client):
    """Mês de outubro/2026 (hoje é 27/10/2026), com plano padrão 50/30/20.

    Fixas: salário R$ 3.000 (confirmado em outubro), aluguel R$ 1.000 (pendente) e internet R$ 100
    (terminou em setembro). Lançamentos: mercado R$ 500, lazer R$ 600 e investimento R$ 400.
    """
    salary = create_income_category(client)
    groceries = create_category(client, name="Mercado")
    housing = create_category(client, name="Moradia", icon="🏠")
    leisure = create_category(client, name="Lazer", default_bucket="wants")
    invest = create_category(client, name="Investimentos", default_bucket="savings")

    pay = create_recurring(
        client,
        salary["id"],
        description="Salário",
        kind="income",
        amount_cents=300_000,
        day_of_month=5,
        payment_method="transfer",
    )
    rent = create_recurring(client, housing["id"], amount_cents=100_000)
    create_recurring(client, housing["id"], description="Internet", amount_cents=10_000, end_month="2026-09")
    client.post(f"/api/recurring/{pay['id']}/confirm", json={"month": "2026-10"})

    create_transaction(client, groceries["id"], amount_cents=50_000, date="2026-10-03")
    create_transaction(client, leisure["id"], amount_cents=60_000, date="2026-10-12")
    create_transaction(client, invest["id"], amount_cents=40_000, date="2026-10-20")
    return {"rent": rent, "housing": housing}


def _flow(realized, pending):
    return {"realized_cents": realized, "pending_cents": pending, "total_cents": realized + pending}


def test_month_summary_separates_realized_and_pending(client, october):
    summary = client.get("/api/summary/month", params={"month": "2026-10"}).json()
    assert summary["month"] == "2026-10"
    assert summary["income"] == _flow(300_000, 0)
    assert summary["needs"] == _flow(50_000, 100_000)
    assert summary["wants"] == _flow(60_000, 0)
    assert summary["savings"] == _flow(40_000, 0)
    assert (summary["balance_cents"], summary["realized_balance_cents"]) == (50_000, 150_000)


def test_month_budget_and_thermometer(client, october):
    summary = client.get("/api/summary/month", params={"month": "2026-10"}).json()
    budget = {
        line["bucket"]: (line["planned_cents"], line["used_cents"], line["used_pct"])
        for line in summary["budget"]
    }
    assert budget == {
        "needs": (150_000, 150_000, 100.0),
        "wants": (90_000, 60_000, 66.7),
        "savings": (60_000, 40_000, 66.7),
    }
    assert summary["thermometer"] == {"status": "controlled", "spending_pct": 70.0, "limit_pct": 80}


def test_month_lists_pending_occurrences_and_category_totals(client, october):
    summary = client.get("/api/summary/month", params={"month": "2026-10"}).json()
    assert [(p["rule_id"], p["description"], p["date"], p["amount_cents"]) for p in summary["pending"]] == [
        (october["rent"]["id"], "Aluguel", "2026-10-10", 100_000)
    ]
    assert [(c["name"], c["total_cents"]) for c in summary["by_category"]] == [
        ("Moradia", 100_000),
        ("Lazer", 60_000),
        ("Mercado", 50_000),
        ("Investimentos", 40_000),
    ]


def test_confirming_and_undoing_a_pending_occurrence(client, october):
    rent_id = october["rent"]["id"]
    confirmed = client.post(f"/api/recurring/{rent_id}/confirm", json={"month": "2026-10"}).json()
    after_confirm = client.get("/api/summary/month", params={"month": "2026-10"}).json()
    assert (after_confirm["needs"], after_confirm["pending"]) == (_flow(150_000, 0), [])
    client.delete(f"/api/transactions/{confirmed['id']}")
    after_undo = client.get("/api/summary/month", params={"month": "2026-10"}).json()
    assert [p["rule_id"] for p in after_undo["pending"]] == [rent_id]


def test_empty_month_has_no_data_instead_of_errors(client):
    summary = client.get("/api/summary/month").json()
    assert summary["month"] == "2026-10"
    assert summary["thermometer"] == {"status": "no_data", "spending_pct": None, "limit_pct": 80}
    assert {line["used_pct"] for line in summary["budget"]} == {None}


def test_month_summary_follows_the_saved_split(client, october):
    client.put("/api/budget-settings", json={"needs_pct": 60, "wants_pct": 30, "savings_pct": 10})
    summary = client.get("/api/summary/month", params={"month": "2026-10"}).json()
    assert [line["planned_cents"] for line in summary["budget"]] == [180_000, 90_000, 30_000]
    assert summary["thermometer"]["limit_pct"] == 90


def test_year_summary_projects_rules_month_by_month(client, october):
    year = client.get("/api/summary/year", params={"year": 2026}).json()
    assert [m["month"] for m in year["months"]] == [f"2026-{n:02d}" for n in range(1, 13)]
    january, october_, december = year["months"][0], year["months"][9], year["months"][11]
    assert (january["income"], january["needs"]) == (_flow(0, 300_000), _flow(0, 110_000))
    assert (october_["income"], october_["needs"]) == (_flow(300_000, 0), _flow(50_000, 100_000))
    assert december["needs"] == _flow(0, 100_000)
    # Renda: 12 salários. Necessidades: 12 aluguéis + 9 internets + mercado.
    assert year["income"]["total_cents"] == 3_600_000
    assert year["needs"]["total_cents"] == 1_340_000
    assert year["balance_cents"] == 3_600_000 - 1_340_000 - 60_000 - 40_000


def test_year_must_be_within_supported_range(client):
    response = client.get("/api/summary/year", params={"year": 1999})
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "year"

from tests.factories import create_category, create_goal, create_transaction

GOAL = {"name": "Reserva de emergência", "icon": "🛟", "target_cents": 1_000_000}


def _contribute(client, goal_id, amount_cents):
    invest = next(
        (c for c in client.get("/api/categories").json() if c["name"] == "Investimentos"), None
    ) or create_category(client, name="Investimentos", default_bucket="savings")
    return create_transaction(client, invest["id"], amount_cents=amount_cents, goal_id=goal_id)


def test_progress_and_monthly_amount_needed(client):
    # Hoje é 27/10/2026; de outubro/2026 a junho/2027 são 9 meses para juntar o que falta.
    goal = create_goal(client, target_date="2027-06-30")
    _contribute(client, goal["id"], 100_000)
    _contribute(client, goal["id"], 50_000)
    listed = client.get("/api/goals").json()[0]
    assert listed["saved_cents"] == 150_000
    assert listed["remaining_cents"] == 850_000
    assert listed["progress_pct"] == 15.0
    assert listed["months_left"] == 9
    assert listed["monthly_needed_cents"] == 94_445  # 850.000 / 9 = 94.444,4 → arredonda para cima


def test_goal_without_date_or_already_reached(client):
    goal = create_goal(client, target_cents=10_000)
    _contribute(client, goal["id"], 12_000)
    listed = client.get("/api/goals").json()[0]
    assert (listed["remaining_cents"], listed["progress_pct"]) == (0, 120.0)
    assert (listed["months_left"], listed["monthly_needed_cents"]) == (None, None)


def test_deleting_a_goal_keeps_its_contributions(client):
    goal = create_goal(client)
    contribution = _contribute(client, goal["id"], 5_000)
    client.delete(f"/api/goals/{goal['id']}")
    remaining = client.get("/api/transactions").json()
    assert [(t["id"], t["goal_id"]) for t in remaining] == [(contribution["id"], None)]


def test_create_and_list_goals(client):
    created = create_goal(client, target_date="2027-06-30")
    assert created["target_date"] == "2027-06-30"
    assert [goal["name"] for goal in client.get("/api/goals").json()] == ["Reserva de emergência"]


def test_goal_needs_a_positive_target(client):
    response = client.post("/api/goals", json=GOAL | {"target_cents": 0})
    assert response.json()["errors"] == [
        {"field": "target_cents", "message": "Informe um valor maior que 0."}
    ]


def test_duplicate_goal_name_is_rejected(client):
    create_goal(client)
    response = client.post("/api/goals", json=GOAL | {"name": "reserva de emergencia"})
    assert response.status_code == 409


def test_update_and_delete_goal(client):
    goal = create_goal(client)
    updated = client.put(f"/api/goals/{goal['id']}", json=GOAL | {"target_cents": 2_000_000})
    assert updated.json()["target_cents"] == 2_000_000
    assert client.delete(f"/api/goals/{goal['id']}").status_code == 204
    missing = client.delete(f"/api/goals/{goal['id']}")
    assert (missing.status_code, missing.json()["detail"]) == (404, "Meta não encontrada.")

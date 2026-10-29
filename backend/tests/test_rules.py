from tests.factories import create_category, create_income_category


def _rule(client, **overrides):
    category = overrides.pop("category_id", None)
    payload = {"pattern": " uber eats ", "match_type": "contains", "category_id": category}
    return client.post("/api/category-rules", json=payload | overrides)


def test_rule_crud_normalizes_pattern(client):
    category = create_category(client, name="Comida fora", default_bucket="wants")
    created = _rule(client, category_id=category["id"])
    assert created.status_code == 201, created.text
    rule = created.json()
    assert (rule["pattern"], rule["match_type"], rule["source"]) == ("UBER EATS", "contains", "learned")

    updated = client.put(
        f"/api/category-rules/{rule['id']}",
        json={"pattern": "Café", "match_type": "exact", "category_id": category["id"]},
    )
    assert updated.status_code == 200
    assert updated.json()["pattern"] == "CAFE"
    assert [r["pattern"] for r in client.get("/api/category-rules").json()] == ["CAFE"]

    assert client.delete(f"/api/category-rules/{rule['id']}").status_code == 204
    assert client.get("/api/category-rules").json() == []


def test_rule_duplicate_conflicts(client):
    category = create_category(client, name="Comida fora", default_bucket="wants")
    assert _rule(client, category_id=category["id"]).status_code == 201
    response = _rule(client, category_id=category["id"], pattern="UBER  EATS")
    assert response.status_code == 409
    assert response.json()["detail"] == "Já existe uma regra igual."


def test_rule_needs_active_category(client):
    category = create_category(client, name="Lazer", default_bucket="wants")
    client.put(
        f"/api/categories/{category['id']}",
        json={"name": "Lazer", "kind": "expense", "default_bucket": "wants", "archived": True},
    )
    response = _rule(client, category_id=category["id"])
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "category_id"


def test_rule_takes_the_kind_of_its_category(client):
    income = create_income_category(client)
    expense = create_category(client, name="Presentes", default_bucket="wants")
    created = _rule(client, category_id=income["id"], pattern="maria", match_type="exact")
    assert created.status_code == 201, created.text
    assert created.json()["kind"] == "income"
    same_name_expense = _rule(client, category_id=expense["id"], pattern="maria", match_type="exact")
    assert same_name_expense.status_code == 201
    assert same_name_expense.json()["kind"] == "expense"
    repeated = _rule(client, category_id=income["id"], pattern="MARIA", match_type="exact")
    assert repeated.status_code == 409
    assert repeated.json()["detail"] == "Já existe uma regra igual."


def test_changing_the_category_changes_the_kind(client):
    income = create_income_category(client)
    expense = create_category(client, name="Presentes", default_bucket="wants")
    other = create_category(client, name="Lazer", default_bucket="wants")
    rule = _rule(client, category_id=expense["id"], pattern="joao", match_type="exact").json()
    moved = client.put(
        f"/api/category-rules/{rule['id']}",
        json={"pattern": "joao", "match_type": "exact", "category_id": income["id"]},
    )
    assert moved.status_code == 200
    assert moved.json()["kind"] == "income"
    _rule(client, category_id=other["id"], pattern="joao", match_type="exact")
    back = client.put(
        f"/api/category-rules/{rule['id']}",
        json={"pattern": "joao", "match_type": "exact", "category_id": expense["id"]},
    )
    assert back.status_code == 409


def test_rule_pattern_needs_two_characters(client):
    category = create_category(client, name="Comida fora", default_bucket="wants")
    response = _rule(client, category_id=category["id"], pattern=" * ")
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "pattern"


def test_missing_rule_is_404(client):
    assert client.delete("/api/category-rules/999").status_code == 404

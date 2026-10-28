def test_defaults_to_50_30_20(client):
    assert client.get("/api/budget-settings").json() == {"needs_pct": 50, "wants_pct": 30, "savings_pct": 20}


def test_update_split(client):
    payload = {"needs_pct": 50, "wants_pct": 20, "savings_pct": 30}
    assert client.put("/api/budget-settings", json=payload).json() == payload
    assert client.get("/api/budget-settings").json() == payload


def test_split_must_add_up_to_100(client):
    response = client.put("/api/budget-settings", json={"needs_pct": 50, "wants_pct": 30, "savings_pct": 30})
    assert response.status_code == 422
    assert response.json()["detail"] == "Os percentuais precisam somar 100% (agora somam 110%)."


def test_each_percentage_stays_between_0_and_100(client):
    response = client.put(
        "/api/budget-settings", json={"needs_pct": 120, "wants_pct": -10, "savings_pct": -10}
    )
    fields = {error["field"] for error in response.json()["errors"]}
    assert fields == {"needs_pct", "wants_pct", "savings_pct"}

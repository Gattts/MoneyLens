"""Toda resposta de erro traz `code` (para o frontend decidir o que fazer) além da mensagem em português."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import DataError, OperationalError

from tests.conftest import PASSWORD, USERNAME


def _code(response) -> str:
    return response.json()["code"]


def test_validation_error(client):
    response = client.post("/api/categories", json={})
    assert (response.status_code, _code(response)) == (422, "validation_error")


def test_not_found_item_and_route(client):
    assert _code(client.delete("/api/categories/999")) == "not_found"
    assert _code(client.get("/api/nao-existe")) == "not_found"


def test_conflict(client):
    body = {"name": "Pets", "kind": "expense", "default_bucket": "wants"}
    client.post("/api/categories", json=body)
    assert _code(client.post("/api/categories", json=body)) == "conflict"


def test_missing_session_is_not_authenticated(anon_client):
    response = anon_client.get("/api/categories")
    assert (response.status_code, _code(response)) == (401, "not_authenticated")


def test_stale_cookie_is_session_expired(anon_client, user):
    anon_client.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
    stale = anon_client.cookies.get("fin_session")
    anon_client.post("/api/auth/logout")
    anon_client.cookies.set("fin_session", stale)
    response = anon_client.get("/api/auth/me")
    assert (response.status_code, _code(response)) == (401, "session_expired")


def test_wrong_login_and_refused_invite_are_not_session_problems(anon_client, user):
    login = anon_client.post("/api/auth/login", json={"username": USERNAME, "password": "errada-123"})
    assert _code(login) == "invalid_credentials"
    activation = anon_client.post(
        "/api/auth/activate", json={"username": "ninguem", "code": "AAAA-AAAA", "password": "senha-boa-123"}
    )
    assert (activation.status_code, _code(activation)) == (401, "invite_refused")


def test_too_many_attempts(anon_client, user):
    for _ in range(5):
        anon_client.post("/api/auth/login", json={"username": USERNAME, "password": "errada-123"})
    response = anon_client.post("/api/auth/login", json={"username": USERNAME, "password": "errada-123"})
    assert (response.status_code, _code(response)) == (429, "too_many_attempts")


def test_payload_too_large(anon_client):
    huge = b"x" * (2 * 1024 * 1024)
    response = anon_client.post("/api/auth/login", content=huge, headers={"content-type": "application/json"})
    assert (response.status_code, _code(response)) == (413, "payload_too_large")


def test_forbidden(other_client):
    assert _code(other_client.get("/api/admin/users")) == "forbidden"


def test_overlong_username_key_is_a_validation_error(client):
    # "ﬀ" (ligadura) vira "ff" na chave: 30 caracteres no nome, 60 na chave (coluna de 50).
    response = client.post("/api/admin/users", json={"username": "ﬀ" * 30})
    assert (response.status_code, response.json()["errors"][0]["field"]) == (422, "username")


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (OperationalError("SELECT 1", {}, Exception("conexão recusada")), 503, "database_unavailable"),
        (DataError("INSERT", {}, Exception("valor longo demais")), 422, "invalid_data"),
        (RuntimeError("falha qualquer"), 500, "internal_error"),
    ],
)
def test_unexpected_and_database_errors(app, error, status, code):
    def boom() -> None:
        raise error

    app.add_api_route("/api/boom", boom)
    with TestClient(app, raise_server_exceptions=False) as browser:
        response = browser.get("/api/boom")
    assert (response.status_code, _code(response)) == (status, code)
    assert "conexão recusada" not in response.text  # detalhes técnicos não vão para a tela

import logging
import re
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from financeiro.models import Category, User

CODE = re.compile(r"[A-HJKMNP-Z2-9]{4}-[A-HJKMNP-Z2-9]{4}")
NEW_PASSWORD = "nova-senha-123"
REFUSED = "Usuário ou código inválido, ou o convite expirou."


@pytest.fixture
def guest(app) -> Iterator[TestClient]:
    """Navegador sem sessão (quem vai fazer o primeiro acesso)."""
    with TestClient(app) as browser:
        yield browser


def invite(client, username: str = "maria") -> dict:
    response = client.post("/api/admin/users", json={"username": username})
    assert response.status_code == 201, response.text
    return response.json()


def activate(browser, username: str, code: str, password: str = NEW_PASSWORD):
    return browser.post("/api/auth/activate", json={"username": username, "code": code, "password": password})


def test_admin_creates_user_and_code_is_shown_once(client):
    created = invite(client)
    assert CODE.fullmatch(created["code"])
    assert (created["user"]["username"], created["user"]["status"], created["user"]["is_admin"]) == (
        "maria",
        "pending",
        False,
    )
    listed = client.get("/api/admin/users").json()
    assert [user["username"] for user in listed] == ["ana", "maria"]
    assert all("code" not in user for user in listed)


def test_non_admin_gets_403(other_client):
    response = other_client.get("/api/admin/users")
    assert response.status_code == 403
    assert response.json()["detail"] == "Só administradores podem fazer isso."


@pytest.mark.parametrize("variant", ["Maria", "MARIA ", "mária", "Mâria"])
def test_duplicate_username_variants(client, variant):
    invite(client)
    response = client.post("/api/admin/users", json={"username": variant})
    assert response.status_code == 409
    assert response.json()["detail"] == "Já existe um usuário com esse nome."


@pytest.mark.parametrize("bad", ["ma", "maria silva", "maria@casa", "mаria"])  # o último tem um "а" cirílico
def test_username_format_is_validated(client, bad):
    response = client.post("/api/admin/users", json={"username": bad})
    assert response.status_code == 422
    assert response.json()["errors"] == [
        {
            "field": "username",
            "message": "Use de 3 a 50 caracteres: letras, números, ponto, hífen ou sublinhado, sem espaços.",
        }
    ]


def test_activation_opens_session_and_consumes_code(client, guest):
    code = invite(client)["code"]
    response = activate(guest, "maria", code)
    assert response.status_code == 200, response.text
    assert response.json() == {"username": "maria", "is_admin": False}
    assert guest.get("/api/auth/me").json()["username"] == "maria"
    again = activate(guest, "maria", code, "outra-senha-123")
    assert (again.status_code, again.json()["detail"]) == (401, REFUSED)


@pytest.mark.parametrize(
    "transform", [str.lower, lambda code: code.replace("-", ""), lambda code: f" {code[:4]} {code[5:]} "]
)
def test_activation_accepts_code_variants(client, guest, transform):
    code = invite(client)["code"]
    assert activate(guest, "maria", transform(code)).status_code == 200


def test_expired_or_wrong_code_and_unknown_user_share_the_message(client, guest, db):
    code = invite(client)["code"]
    assert activate(guest, "maria", "AAAA-AAAA").json()["detail"] == REFUSED
    assert activate(guest, "ninguem", code).json()["detail"] == REFUSED
    maria = db.scalar(select(User).where(User.username_key == "maria"))
    maria.invite_expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()
    expired = activate(guest, "maria", code)
    assert (expired.status_code, expired.json()["detail"]) == (401, REFUSED)


def test_activation_is_rate_limited_with_login(client, guest):
    invite(client)
    for _ in range(5):
        activate(guest, "maria", "AAAA-AAAA")
    assert activate(guest, "maria", "AAAA-AAAA").status_code == 429


def test_short_password_is_refused(client, guest):
    code = invite(client)["code"]
    response = activate(guest, "maria", code, "curta")
    assert response.json()["errors"] == [{"field": "password", "message": "Use de 8 a 128 caracteres."}]


def test_pending_account_cannot_login(client, guest):
    invite(client)
    response = guest.post("/api/auth/login", json={"username": "maria", "password": "qualquer-coisa"})
    assert (response.status_code, response.json()["detail"]) == (401, "Usuário ou senha incorretos.")


def test_login_and_activation_ignore_username_case(client, guest):
    code = invite(client)["code"]
    assert activate(guest, "Maria ", code).status_code == 200
    guest.post("/api/auth/logout")
    assert (
        guest.post("/api/auth/login", json={"username": "MARIA", "password": NEW_PASSWORD}).status_code == 200
    )


def test_new_invite_drops_sessions_and_old_password(client, guest):
    created = invite(client)
    activate(guest, "maria", created["code"])
    renewed = client.post(f"/api/admin/users/{created['user']['id']}/invite")
    assert renewed.status_code == 200
    assert renewed.json()["user"]["status"] == "pending"
    assert guest.get("/api/auth/me").status_code == 401
    login = guest.post("/api/auth/login", json={"username": "maria", "password": NEW_PASSWORD})
    assert login.status_code == 401
    assert activate(guest, "maria", renewed.json()["code"]).status_code == 200


def test_admin_cannot_reset_own_invite(client, user):
    assert client.post(f"/api/admin/users/{user.id}/invite").status_code == 409


def test_delete_only_pending_users_and_never_self(client, guest, user):
    pending = invite(client, "maria")["user"]
    active = invite(client, "joana")
    activate(guest, "joana", active["code"])
    assert client.delete(f"/api/admin/users/{active['user']['id']}").status_code == 409
    assert client.delete(f"/api/admin/users/{user.id}").status_code == 409
    assert client.delete(f"/api/admin/users/{pending['id']}").status_code == 204
    assert [u["username"] for u in client.get("/api/admin/users").json()] == ["ana", "joana"]


def test_delete_pending_user_removes_its_defaults(client, db):
    pending = invite(client)["user"]
    client.delete(f"/api/admin/users/{pending['id']}")
    remaining = db.scalar(select(func.count()).select_from(Category).where(Category.user_id == pending["id"]))
    assert remaining == 0


def test_new_user_starts_with_default_package(client, guest):
    activate(guest, "maria", invite(client)["code"])
    assert len(guest.get("/api/categories").json()) == 24
    assert guest.get("/api/budget-settings").json() == {"needs_pct": 50, "wants_pct": 30, "savings_pct": 20}


def test_me_reports_admin_flag(client):
    assert client.get("/api/auth/me").json() == {"username": "ana", "is_admin": True}


def test_logs_never_contain_codes_or_passwords(client, guest, caplog):
    caplog.set_level(logging.INFO)
    code = invite(client)["code"]
    activate(guest, "maria", code)
    assert code not in caplog.text
    assert code.replace("-", "") not in caplog.text
    assert NEW_PASSWORD not in caplog.text

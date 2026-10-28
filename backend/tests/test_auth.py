from fastapi.testclient import TestClient

from financeiro.app import create_app
from tests.conftest import PASSWORD, USERNAME

PUBLIC_ROUTES = {"/api/auth/login", "/api/auth/logout", "/api/health"}


def login(client, password=PASSWORD, username=USERNAME):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def test_login_with_valid_credentials_opens_a_session(anon_client, user):
    response = login(anon_client)
    assert response.status_code == 200
    assert response.json() == {"username": USERNAME}
    assert anon_client.get("/api/auth/me").json() == {"username": USERNAME}


def test_wrong_password_and_unknown_user_get_the_same_generic_message(anon_client, user):
    wrong_password = login(anon_client, password="errada-123")
    unknown_user = login(anon_client, username="bruno")
    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json()["detail"] == unknown_user.json()["detail"] == "Usuário ou senha incorretos."


def test_every_api_route_except_public_ones_requires_login(app, anon_client):
    checked = 0
    for path, operations in app.openapi()["paths"].items():
        if path in PUBLIC_ROUTES:
            continue
        for method in operations:
            response = anon_client.request(method.upper(), path.replace("{item_id}", "1"))
            assert response.status_code == 401, f"{method.upper()} {path} respondeu {response.status_code}"
            checked += 1
    assert checked > 0


def test_logout_ends_the_session(client):
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_password_change_invalidates_sessions_opened_before(client, db, user):
    user.session_version += 1
    db.commit()
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Faça login para continuar."


def test_repeated_failed_logins_are_throttled_even_with_the_right_password(anon_client, user, settings):
    for _ in range(settings.login_max_attempts):
        assert login(anon_client, password="errada-123").status_code == 401
    blocked = login(anon_client)
    assert blocked.status_code == 429
    assert "Muitas tentativas" in blocked.json()["detail"]
    assert int(blocked.headers["Retry-After"]) > 0


def test_successful_login_resets_the_failure_count(anon_client, user, settings):
    for _ in range(settings.login_max_attempts - 1):
        login(anon_client, password="errada-123")
    assert login(anon_client).status_code == 200
    for _ in range(settings.login_max_attempts - 1):
        assert login(anon_client, password="errada-123").status_code == 401


def test_session_cookie_is_http_only_and_same_site_strict(anon_client, user):
    cookie = login(anon_client).headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=strict" in cookie


def test_oversized_password_is_rejected_before_hashing(anon_client, user):
    response = login(anon_client, password="x" * 10_000)
    assert response.status_code == 422


def test_untrusted_host_header_is_rejected(anon_client):
    response = anon_client.get("/api/health", headers={"host": "atacante.example"})
    assert response.status_code == 400


def test_security_headers_are_sent(anon_client):
    headers = anon_client.get("/api/health").headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in headers["content-security-policy"]
    assert headers["cache-control"] == "no-store"


def test_interactive_docs_are_disabled_by_default(anon_client):
    assert anon_client.get("/api/docs").status_code == 404
    assert anon_client.get("/docs").status_code == 404
    assert anon_client.get("/api/openapi.json").status_code == 404


def test_interactive_docs_can_be_enabled(settings):
    settings.enable_docs = True
    with TestClient(create_app(settings)) as docs_client:
        assert docs_client.get("/api/docs").status_code == 200
        assert docs_client.get("/api/openapi.json").status_code == 200

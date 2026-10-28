"""Proteções apontadas na revisão de segurança."""

import stat

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from financeiro.app import create_app
from financeiro.cli import run_migrations
from financeiro.config import Settings
from financeiro.security import load_secret_key
from tests.conftest import PASSWORD, USERNAME


def test_logout_invalidates_cookies_copied_before_it(anon_client, user):
    anon_client.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
    stolen_cookie = anon_client.cookies.get("fin_session")
    anon_client.post("/api/auth/logout")
    anon_client.cookies.set("fin_session", stolen_cookie)
    assert anon_client.get("/api/auth/me").status_code == 401


def test_logout_without_session_is_harmless(anon_client):
    assert anon_client.post("/api/auth/logout").status_code == 204


def test_oversized_body_is_rejected_before_being_read(anon_client):
    huge = '{"username": "ana", "password": "' + "x" * (2 * 1024 * 1024) + '"}'
    response = anon_client.post("/api/auth/login", content=huge, headers={"content-type": "application/json"})
    assert response.status_code == 413
    assert response.json()["detail"] == "Requisição grande demais."


def test_oversized_chunked_body_without_length_is_rejected(anon_client):
    def chunks():
        yield b'{"username": "ana", "password": "'
        for _ in range(64):
            yield b"x" * 64 * 1024
        yield b'"}'

    response = anon_client.post(
        "/api/auth/login", content=chunks(), headers={"content-type": "application/json"}
    )
    assert response.status_code == 413


def test_normal_requests_still_pass_the_size_limit(client):
    response = client.post(
        "/api/categories", json={"name": "Pets", "kind": "expense", "default_bucket": "wants"}
    )
    assert response.status_code == 201


def test_render_health_check_host_is_accepted(tmp_path, monkeypatch):
    # O health check do Render chega com o Host do serviço; recusá-lo (400) cancelaria o deploy.
    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", "financeiro-api.onrender.com")
    settings = Settings(_env_file=None, database_url="sqlite://", secret_key="x" * 40, frontend_dist=tmp_path)
    app = create_app(settings)
    render = TestClient(app, base_url="https://financeiro-api.onrender.com")
    assert render.get("/api/health").status_code == 200
    assert TestClient(app, base_url="https://outro.exemplo.com").get("/api/health").status_code == 400


def test_empty_frontend_dist_does_not_expose_the_working_directory(tmp_path, monkeypatch):
    # Com FIN_FRONTEND_DIST= vazio, o caminho virava a pasta atual e o backend servia o próprio .env.
    env_file = tmp_path / ".env"
    env_file.write_text(f"FIN_FRONTEND_DIST=\nFIN_DATABASE_URL=sqlite://\nFIN_SECRET_KEY={'s' * 40}\n")
    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app(Settings(_env_file=env_file)), base_url="http://localhost")
    assert "FIN_SECRET_KEY" not in client.get("/.env").text


def test_folder_without_index_html_is_not_served_as_frontend(tmp_path):
    (tmp_path / "anotacoes.txt").write_text("não é um build do frontend")
    settings = Settings(_env_file=None, database_url="sqlite://", secret_key="x" * 40, frontend_dist=tmp_path)
    client = TestClient(create_app(settings), base_url="http://localhost")
    assert client.get("/anotacoes.txt").status_code == 404


def test_database_and_data_folder_are_private(tmp_path):
    settings = Settings(_env_file=None, data_dir=tmp_path / "dados", secret_key="x" * 40)
    run_migrations(settings)
    assert stat.S_IMODE((tmp_path / "dados").stat().st_mode) == 0o700
    assert stat.S_IMODE((tmp_path / "dados" / "financeiro.db").stat().st_mode) == 0o600


def test_generated_secret_key_is_private_and_stable(tmp_path):
    settings = Settings(_env_file=None, data_dir=tmp_path)
    first = load_secret_key(settings)
    assert load_secret_key(settings) == first
    assert len(first) >= 32
    assert stat.S_IMODE((tmp_path / "secret_key").stat().st_mode) == 0o600


def test_hsts_only_when_served_over_https(settings):
    with TestClient(create_app(settings)) as plain:
        assert "strict-transport-security" not in plain.get("/api/health").headers
    settings.cookie_secure = True
    with TestClient(create_app(settings)) as secure:
        assert secure.get("/api/health").headers["strict-transport-security"].startswith("max-age=")


def test_database_conflict_is_logged_without_personal_values(client, monkeypatch, caplog):
    # Simula duas requisições que passam juntas pela checagem de nome: quem barra é o banco.
    monkeypatch.setattr("financeiro.routers.categories.ensure_unique_name", lambda *args, **kwargs: None)
    payload = {"name": "Consulta Psiquiatra Sigilosa", "kind": "expense", "default_bucket": "needs"}
    assert client.post("/api/categories", json=payload).status_code == 201
    response = client.post("/api/categories", json=payload)
    assert response.status_code == 409
    assert response.json()["detail"] == "A operação conflita com dados já cadastrados."
    assert "categories" in caplog.text  # diz qual restrição falhou (SQLite e Postgres)
    assert "Sigilosa" not in caplog.text


PROXY_SECRET = "segredo-do-proxy-cloudflare-com-32-caracteres"


def _fail_login(test_client, ip, secret=PROXY_SECRET):
    headers = {"x-forwarded-for": ip, "x-proxy-secret": secret}
    return test_client.post(
        "/api/auth/login", json={"username": "ana", "password": "errada"}, headers=headers
    )


def test_behind_the_proxy_each_real_visitor_has_its_own_login_limit(settings, anon_client, user):
    settings.proxy_secret = PROXY_SECRET
    for _ in range(settings.login_max_attempts):
        _fail_login(anon_client, "203.0.113.7")
    assert _fail_login(anon_client, "203.0.113.7").status_code == 429
    assert _fail_login(anon_client, "198.51.100.20").status_code == 401  # outra pessoa não é bloqueada


def test_forged_forwarded_ip_without_the_secret_does_not_escape_the_limit(settings, anon_client, user):
    settings.proxy_secret = PROXY_SECRET
    for attempt in range(settings.login_max_attempts):
        _fail_login(anon_client, f"10.0.0.{attempt}", secret="chute")
    assert _fail_login(anon_client, "10.0.0.99", secret="chute").status_code == 429


def test_proxy_only_mode_refuses_requests_that_skip_the_worker(settings, anon_client, user):
    settings.proxy_secret = PROXY_SECRET
    settings.proxy_only = True
    direct = anon_client.post("/api/auth/login", json={"username": "ana", "password": "senha-segura-123"})
    assert (direct.status_code, direct.json()["detail"]) == (403, "Acesso direto à API não é permitido.")
    via_worker = anon_client.post(
        "/api/auth/login",
        json={"username": "ana", "password": "senha-segura-123"},
        headers={"x-proxy-secret": PROXY_SECRET},
    )
    assert via_worker.status_code == 200
    assert anon_client.get("/api/health").status_code == 200  # health check da plataforma continua livre


def test_proxy_only_mode_requires_the_secret():
    with pytest.raises(ValidationError, match="FIN_PROXY_SECRET"):
        Settings(_env_file=None, proxy_only=True)


def test_upload_route_accepts_up_to_5_mib_and_others_keep_1_mib(anon_client):
    two_mib = b"x" * (2 * 1024 * 1024)
    headers = {"content-type": "application/octet-stream"}
    assert anon_client.post("/api/invoice-imports", content=two_mib, headers=headers).status_code != 413
    six_mib = b"x" * (6 * 1024 * 1024)
    assert anon_client.post("/api/invoice-imports", content=six_mib, headers=headers).status_code == 413
    assert anon_client.post("/api/auth/login", content=two_mib, headers=headers).status_code == 413

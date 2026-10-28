import json

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from financeiro.cli import main, set_password
from financeiro.config import Settings
from financeiro.models import User
from financeiro.security import verify_password


def _settings(tmp_path) -> Settings:
    return Settings(_env_file=None, data_dir=tmp_path, secret_key="x" * 40)


def _run(settings, passwords, username=None, typed_username="ana"):
    answers = iter(passwords)
    messages: list[str] = []
    code = set_password(
        settings,
        username,
        read_password=lambda _prompt: next(answers),
        read_line=lambda _prompt: typed_username,
        out=messages.append,
    )
    return code, messages


def _users(settings):
    with Session(create_engine(settings.resolved_database_url)) as session:
        return session.scalars(select(User)).all()


def test_first_run_creates_the_user(tmp_path):
    settings = _settings(tmp_path)
    code, messages = _run(settings, ["senha-boa-123", "senha-boa-123"])
    assert code == 0
    [user] = _users(settings)
    assert user.username == "ana"
    assert verify_password(user.password_hash, "senha-boa-123")
    assert "criado" in messages[-1]


def test_changing_the_password_invalidates_sessions(tmp_path):
    settings = _settings(tmp_path)
    _run(settings, ["senha-boa-123", "senha-boa-123"])
    code, _ = _run(settings, ["outra-senha-456", "outra-senha-456"])
    [user] = _users(settings)
    assert code == 0
    assert verify_password(user.password_hash, "outra-senha-456")
    assert user.session_version == 2


def test_rejects_short_or_mismatched_passwords(tmp_path):
    settings = _settings(tmp_path)
    assert _run(settings, ["curta", "curta"])[0] == 1
    assert _run(settings, ["senha-boa-123", "senha-diferente"])[0] == 1
    assert _users(settings) == []


def test_rejects_blank_username(tmp_path):
    settings = _settings(tmp_path)
    code, messages = _run(settings, ["senha-boa-123", "senha-boa-123"], typed_username="   ")
    assert code == 1
    assert "usuário" in messages[-1].lower()


def _serve(monkeypatch, settings, *argv):
    calls: list[dict] = []
    monkeypatch.setattr("financeiro.cli.get_settings", lambda: settings)
    monkeypatch.setattr("financeiro.cli.run_migrations", lambda _settings: None)
    monkeypatch.setattr("financeiro.cli.uvicorn.run", lambda *args, **kwargs: calls.append(kwargs))
    assert main(["serve", *argv]) == 0
    return calls[0]


def test_serving_to_the_network_without_secure_cookie_warns(monkeypatch, tmp_path, capsys):
    _serve(monkeypatch, _settings(tmp_path), "--host", "0.0.0.0")
    assert "FIN_COOKIE_SECURE" in capsys.readouterr().err


def test_serving_locally_or_with_secure_cookie_does_not_warn(monkeypatch, tmp_path, capsys):
    _serve(monkeypatch, _settings(tmp_path))
    secure = _settings(tmp_path)
    secure.cookie_secure = True
    _serve(monkeypatch, secure, "--host", "0.0.0.0")
    assert capsys.readouterr().err == ""


def test_openapi_command_prints_the_api_contract_without_touching_data(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("FIN_DATA_DIR", str(tmp_path / "nao-deve-existir"))
    assert main(["openapi"]) == 0
    contract = json.loads(capsys.readouterr().out)
    assert "/api/transactions" in contract["paths"]
    assert "TransactionOut" in contract["components"]["schemas"]
    assert not (tmp_path / "nao-deve-existir").exists()


def test_server_does_not_announce_itself(monkeypatch, tmp_path):
    assert _serve(monkeypatch, _settings(tmp_path))["server_header"] is False


def test_uvicorn_does_not_rewrite_client_ip_from_forwarded_headers(monkeypatch, tmp_path):
    # Quem decide se o X-Forwarded-For vale é client_address(), com o segredo do proxy.
    assert _serve(monkeypatch, _settings(tmp_path))["proxy_headers"] is False

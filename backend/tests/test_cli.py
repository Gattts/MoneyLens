import json
from datetime import UTC, datetime, timedelta

import numpy as np
import onnxruntime
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from financeiro.cli import main, set_password
from financeiro.config import Settings
from financeiro.models import Category, User
from financeiro.security import hash_password, verify_password


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
    assert contract["info"]["title"] == "MoneyLens"
    assert not (tmp_path / "nao-deve-existir").exists()


def test_server_does_not_announce_itself(monkeypatch, tmp_path):
    assert _serve(monkeypatch, _settings(tmp_path))["server_header"] is False


def test_uvicorn_does_not_rewrite_client_ip_from_forwarded_headers(monkeypatch, tmp_path):
    # Quem decide se o X-Forwarded-For vale é client_address(), com o segredo do proxy.
    assert _serve(monkeypatch, _settings(tmp_path))["proxy_headers"] is False


def test_set_password_on_empty_database_creates_activated_admin(tmp_path):
    settings = _settings(tmp_path)
    assert _run(settings, ["senha-boa-123", "senha-boa-123"], typed_username="Ana.Silva")[0] == 0
    [user] = _users(settings)
    assert (user.username_key, user.is_admin, user.activated_at is not None) == ("ana.silva", True, True)
    with Session(create_engine(settings.resolved_database_url)) as session:
        assert (
            session.scalar(select(func.count()).select_from(Category).where(Category.user_id == user.id))
            == 24
        )


def _add_pending_user(settings, username: str) -> None:
    with Session(create_engine(settings.resolved_database_url)) as session:
        session.add(
            User(
                username=username,
                username_key=username.lower(),
                password_hash=hash_password("senha-aleatoria-qualquer"),
                session_version=1,
                invite_code_hash=hash_password("AAAABBBB"),
                invite_expires_at=datetime.now(UTC) + timedelta(days=7),
            )
        )
        session.commit()


def test_set_password_with_several_users_targets_the_admin(tmp_path):
    settings = _settings(tmp_path)
    _run(settings, ["senha-boa-123", "senha-boa-123"])  # ana, administradora
    _add_pending_user(settings, "bia")
    assert _run(settings, ["outra-senha-456", "outra-senha-456"])[0] == 0
    users = {user.username: user for user in _users(settings)}
    assert verify_password(users["ana"].password_hash, "outra-senha-456")
    assert not verify_password(users["bia"].password_hash, "outra-senha-456")


def test_set_password_by_username_activates_and_clears_invite(tmp_path):
    settings = _settings(tmp_path)
    _run(settings, ["senha-boa-123", "senha-boa-123"])
    _add_pending_user(settings, "bia")
    assert _run(settings, ["senha-da-bia-1", "senha-da-bia-1"], username="BIA")[0] == 0
    bia = next(user for user in _users(settings) if user.username == "bia")
    assert verify_password(bia.password_hash, "senha-da-bia-1")
    assert (bia.activated_at is not None, bia.invite_code_hash, bia.username) == (True, None, "bia")


def test_set_password_for_unknown_username_is_refused(tmp_path):
    settings = _settings(tmp_path)
    _run(settings, ["senha-boa-123", "senha-boa-123"])
    code, messages = _run(settings, ["senha-boa-123", "senha-boa-123"], username="ninguem")
    assert code == 1
    assert "não encontrado" in messages[-1]


def test_ml_commands_explain_how_to_install_the_ml_group(monkeypatch, capsys):
    monkeypatch.setattr("financeiro.cli.ml_available", lambda: False)
    monkeypatch.setattr("financeiro.cli.get_settings", _must_not_read_settings)
    for command in ("treinar-base", "treinar"):
        assert main([command]) == 1
        assert "Instale as dependências de ML: uv sync --group ml" in capsys.readouterr().out


def test_train_base_writes_the_synthetic_model_without_touching_the_database(monkeypatch, tmp_path, capsys):
    pytest.importorskip("torch")
    monkeypatch.setattr("financeiro.cli.get_settings", _must_not_read_settings)
    monkeypatch.setattr("financeiro.forecast.train.BASE_PRETRAIN", {"histories": 2, "months": 6, "epochs": 5})
    assert main(["treinar-base", "--destino", str(tmp_path)]) == 0
    assert (tmp_path / "base.pt").stat().st_size > 0
    session = onnxruntime.InferenceSession((tmp_path / "base.onnx").read_bytes())
    (out,) = session.run(["quantiles"], {"features": np.zeros((3, 7), dtype=np.float32)})
    assert out.shape == (3, 2)
    assert "Modelo base gravado" in capsys.readouterr().out


def test_train_never_migrates_nor_serves(monkeypatch, tmp_path, capsys):
    """Sem a tabela de modelos, explica e para: quem migra o banco é a publicação, não o treino."""
    monkeypatch.setattr("financeiro.cli.ml_available", lambda: True)
    monkeypatch.setattr("financeiro.cli.get_settings", lambda: _settings(tmp_path))
    monkeypatch.setattr("financeiro.cli.run_migrations", _must_not_read_settings)
    monkeypatch.setattr("financeiro.cli.uvicorn.run", _must_not_read_settings)
    assert main(["treinar"]) == 1
    assert "O banco ainda não tem a tabela de modelos" in capsys.readouterr().out


def _must_not_read_settings():
    raise AssertionError("o comando não pode ler as configurações (o .env aponta para produção)")

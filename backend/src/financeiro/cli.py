"""Linha de comando: `financeiro serve`, `financeiro migrate` e `financeiro set-password`."""

import argparse
import getpass
import json
import secrets
import sys
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import uvicorn
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from financeiro.app import create_app
from financeiro.config import Settings, get_settings
from financeiro.db import create_db_engine
from financeiro.domain.months import first_day
from financeiro.domain.usernames import username_key
from financeiro.errors import AppError
from financeiro.forecast import ML_MISSING, PACKAGE_DIR, ml_available
from financeiro.forecast.features import history_months
from financeiro.forecast.history import load_history
from financeiro.forecast.store import save_model
from financeiro.models import User
from financeiro.security import hash_password
from financeiro.services.users import (
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    find_user,
    seed_defaults,
    validate_username,
)
from financeiro.storage import ensure_private_dir

MAX_USERNAME_LENGTH = 50
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
INSECURE_NETWORK_WARNING = (
    "Atenção: servindo para a rede sem FIN_COOKIE_SECURE=true. O cookie de sessão poderia trafegar sem "
    "criptografia. Use HTTPS (proxy reverso) e ligue essa opção; veja o README."
)


def run_migrations(settings: Settings) -> None:
    if settings.database_url is None:
        ensure_private_dir(settings.data_dir)
    config = Config()
    config.set_main_option("script_location", "financeiro:migrations")
    # O ConfigParser do Alembic interpreta "%"; uma senha de banco na URL poderia conter um.
    config.set_main_option("sqlalchemy.url", settings.resolved_database_url.replace("%", "%%"))
    command.upgrade(config, "head")


def set_password(
    settings: Settings,
    username: str | None,
    read_password: Callable[[str], str] = getpass.getpass,
    read_line: Callable[[str], str] = input,
    out: Callable[[str], None] = print,
) -> int:
    """Banco vazio: cria o administrador. Senão troca a senha do usuário informado (padrão: o admin)."""
    run_migrations(settings)
    engine = create_db_engine(settings.resolved_database_url)
    try:
        with Session(engine) as session:
            empty = session.scalar(select(User.id).limit(1)) is None
            target = None if empty else _password_target(session, username)
            if not empty and target is None:
                out(f"Erro: usuário {username!r} não encontrado.")
                return 1
            name = _new_admin_name(username, read_line, out) if empty else ""
            password = _read_new_password(read_password, out)
            if password is None or (empty and not name):
                return 1
            if target is None:
                message = _create_admin(session, name, password)
            else:
                # Também serve para quem esqueceu a senha: ativa a conta e invalida o convite em aberto.
                target.password_hash = hash_password(password)
                target.activated_at = target.activated_at or datetime.now(UTC)
                target.invite_code_hash = target.invite_expires_at = None
                target.session_version += 1
                message = f"Senha de {target.username!r} atualizada. Sessões abertas foram encerradas."
            session.commit()
    finally:
        engine.dispose()
    out(message)
    return 0


def _password_target(session: Session, username: str | None) -> User | None:
    if username:
        return find_user(session, username)
    return session.scalar(select(User).order_by(User.is_admin.desc(), User.id).limit(1))


def _new_admin_name(username: str | None, read_line: Callable[[str], str], out: Callable[[str], None]) -> str:
    try:
        return validate_username(username or read_line("Usuário: "))
    except AppError as error:
        out(f"Erro: nome de usuário inválido. {error.message}")
        return ""


def _read_new_password(read_password: Callable[[str], str], out: Callable[[str], None]) -> str | None:
    password = read_password("Nova senha: ")
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        out(f"Erro: a senha precisa ter de {MIN_PASSWORD_LENGTH} a {MAX_PASSWORD_LENGTH} caracteres.")
        return None
    if read_password("Repita a nova senha: ") != password:
        out("Erro: as senhas não conferem.")
        return None
    return password


def _create_admin(session: Session, name: str, password: str) -> str:
    """Primeiro usuário do banco: administrador, já ativado e com o pacote padrão."""
    admin = User(
        username=name,
        username_key=username_key(name),
        password_hash=hash_password(password),
        is_admin=True,
        activated_at=datetime.now(UTC),
    )
    session.add(admin)
    session.flush()
    seed_defaults(session, admin.id)
    return f"Usuário {name!r} criado como administrador. Agora é só entrar pelo navegador."


def _command_without_settings(args: argparse.Namespace) -> int | None:
    """Comandos que não leem as configurações (o `.env` pode apontar para o banco de produção)."""
    if args.command == "openapi":
        print(json.dumps(openapi_contract(), ensure_ascii=False, indent=2))
        return 0
    if args.command in {"treinar-base", "treinar"} and not ml_available():
        print(ML_MISSING)
        return 1
    if args.command == "treinar-base":
        return train_base_command(Path(args.destino))
    return None


def train_command(settings: Settings, username: str | None, today: date | None = None) -> int:
    """Treina o modelo de cada usuário (ou só do informado) e grava no banco. Imprime só métricas."""
    engine = create_db_engine(settings.resolved_database_url)
    try:
        if not inspect(engine).has_table("forecast_models"):
            print("O banco ainda não tem a tabela de modelos. Publique a versão nova antes de treinar.")
            return 1
        # O PyTorch só é importado depois de conferir o banco (o teste acima roda sem o grupo ml, como no CI).
        from financeiro.forecast.train import MIN_MONTHS, export_onnx, finetune, load_base  # noqa: PLC0415

        until = first_day(today or date.today())
        base = load_base()
        with Session(engine) as session:
            users = _users_to_train(session, username)
            if username and not users:
                print(f"Erro: usuário {username!r} não encontrado.")
                return 1
            for user in users:
                expenses = load_history(session, user.id, until)
                months = history_months(expenses, until)
                if len(months) < MIN_MONTHS:
                    print(
                        f"{user.username}: só {len(months)} mês(es) fechado(s); continua com o modelo base."
                    )
                    continue
                result = finetune(base, expenses, until)
                saved = save_model(
                    session, user.id, export_onnx(result.model), result.metrics, trained_until=months[-1]
                )
                print(_metrics_line(user.username, result.metrics, saved.version))
    finally:
        engine.dispose()
    return 0


def _users_to_train(session: Session, username: str | None) -> list[User]:
    if username:
        found = find_user(session, username)
        return [found] if found else []
    return list(session.scalars(select(User).order_by(User.id)).all())


def _metrics_line(username: str, metrics: dict[str, float | int], version: int) -> str:
    def reais(cents: float | int) -> str:
        return f"R$ {cents / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    coverage = round(float(metrics["coverage_p90"]) * 100)
    return (
        f"{username}: {metrics['months']} meses, erro médio do modelo {reais(metrics['mae_model_cents'])}, "
        f"da estatística {reais(metrics['mae_baseline_cents'])}, teto cobriu {coverage}% — versão {version}"
    )


def train_base_command(output_dir: Path) -> int:
    """Não lê o banco nem as configurações: o modelo base só usa dados inventados."""
    from financeiro.forecast.train import train_base  # noqa: PLC0415 - o PyTorch só existe com o grupo ml

    train_base(output_dir)
    print(f"Modelo base gravado em {output_dir}.")
    return 0


def openapi_contract() -> dict[str, Any]:
    """Contrato da API, base dos tipos do frontend. Usa banco em memória: não lê nem cria arquivos."""
    settings = Settings(_env_file=None, database_url="sqlite://", secret_key=secrets.token_urlsafe(48))
    return create_app(settings).openapi()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="financeiro", description="Ferramenta de acompanhamento financeiro."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="aplica as migrações e inicia o servidor")
    serve.add_argument("--host", default="127.0.0.1", help="endereço de escuta (padrão: só esta máquina)")
    serve.add_argument("--port", type=int, default=8000, help="porta (padrão: 8000)")
    serve.add_argument("--reload", action="store_true", help="reinicia ao editar o código (desenvolvimento)")
    commands.add_parser("migrate", help="aplica as migrações do banco")
    password = commands.add_parser("set-password", help="cria o usuário ou troca a senha")
    password.add_argument("--username", help="nome de usuário (padrão: o atual)")
    commands.add_parser("openapi", help="imprime o contrato da API em JSON (gera os tipos do frontend)")
    base = commands.add_parser("treinar-base", help="gera o modelo base de previsão com dados sintéticos")
    base.add_argument("--destino", default=str(PACKAGE_DIR), help="pasta dos arquivos (padrão: o pacote)")
    train = commands.add_parser("treinar", help="treina o modelo de previsão de cada usuário (grupo ml)")
    train.add_argument("--username", help="treina só este usuário")
    args = parser.parse_args(argv)
    early = _command_without_settings(args)
    if early is not None:
        return early

    settings = get_settings()
    if args.command == "treinar":
        return train_command(settings, args.username)
    if args.command == "set-password":
        return set_password(settings, args.username)
    run_migrations(settings)
    if args.command == "migrate":
        print("Banco de dados atualizado.")
        return 0
    if args.host not in LOCAL_HOSTS and not settings.cookie_secure:
        print(INSECURE_NETWORK_WARNING, file=sys.stderr)
    uvicorn.run(
        "financeiro.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
        server_header=False,
        # Quem decide se X-Forwarded-For vale é security.client_address(), conferindo o segredo do proxy.
        proxy_headers=False,
    )
    return 0

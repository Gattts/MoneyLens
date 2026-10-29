"""Linha de comando: `financeiro serve`, `financeiro migrate` e `financeiro set-password`."""

import argparse
import getpass
import json
import secrets
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import uvicorn
from alembic import command
from alembic.config import Config
from sqlalchemy import select
from sqlalchemy.orm import Session

from financeiro.app import create_app
from financeiro.config import Settings, get_settings
from financeiro.db import create_db_engine
from financeiro.domain.usernames import username_key
from financeiro.models import User
from financeiro.security import hash_password
from financeiro.services.users import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH, seed_defaults
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
    """Cria o usuário único ou troca a senha dele. Devolve o código de saída do processo."""
    run_migrations(settings)
    engine = create_db_engine(settings.resolved_database_url)
    try:
        with Session(engine) as session:
            user = session.scalars(select(User)).first()
            name = (username or (user.username if user else read_line("Usuário: "))).strip()
            if not 1 <= len(name) <= MAX_USERNAME_LENGTH:
                out(f"Erro: o usuário precisa ter de 1 a {MAX_USERNAME_LENGTH} caracteres.")
                return 1
            password = read_password("Nova senha: ")
            if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
                out(f"Erro: a senha precisa ter de {MIN_PASSWORD_LENGTH} a {MAX_PASSWORD_LENGTH} caracteres.")
                return 1
            if read_password("Repita a nova senha: ") != password:
                out("Erro: as senhas não conferem.")
                return 1
            if user is None:
                # Banco vazio: o primeiro usuário é o administrador, já ativado e com o pacote padrão.
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
                message = f"Usuário {name!r} criado. Agora é só entrar pelo navegador."
            else:
                user.username, user.username_key = name, username_key(name)
                user.password_hash = hash_password(password)
                user.session_version += 1
                message = "Senha atualizada. Sessões abertas em outros navegadores foram encerradas."
            session.commit()
    finally:
        engine.dispose()
    out(message)
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
    args = parser.parse_args(argv)

    if args.command == "openapi":
        print(json.dumps(openapi_contract(), ensure_ascii=False, indent=2))
        return 0

    settings = get_settings()
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

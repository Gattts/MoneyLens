"""Conexão com o banco e sessão por requisição."""

from collections.abc import Iterator
from typing import Annotated, Any

from fastapi import Depends, Request
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from financeiro.storage import prepare_sqlite_file


def create_db_engine(url: str) -> Engine:
    if not url.startswith("sqlite"):
        return create_engine(
            url,
            # O pooler do Supabase encerra conexões ociosas; testar antes de usar evita erro no 1º acesso.
            pool_pre_ping=True,
            pool_recycle=300,
            # O pooler em modo transação (porta 6543) não suporta prepared statements.
            connect_args={"prepare_threshold": None},
        )
    in_memory = url in ("sqlite://", "sqlite:///:memory:")
    prepare_sqlite_file(url)
    engine = create_engine(
        url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool if in_memory else None,
    )
    event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def _enable_sqlite_foreign_keys(dbapi_connection: Any, _connection_record: Any) -> None:
    # O SQLite só aplica chaves estrangeiras (RESTRICT / SET NULL) com este PRAGMA ligado.
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.sessionmaker() as session:
        yield session


DbSession = Annotated[Session, Depends(get_session)]

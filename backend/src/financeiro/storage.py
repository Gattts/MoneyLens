"""Arquivos de dados privados: só o dono do processo lê o banco e a chave de sessão."""

import contextlib
import os
from pathlib import Path

from sqlalchemy.engine import make_url

PRIVATE_DIR_MODE = 0o700
PRIVATE_FILE_MODE = 0o600


def ensure_private_dir(path: Path) -> None:
    """Cria a pasta com acesso só do dono, ou fecha o acesso se ela já existir."""
    path.mkdir(mode=PRIVATE_DIR_MODE, parents=True, exist_ok=True)
    path.chmod(PRIVATE_DIR_MODE)  # o mode do mkdir passa pelo umask; o chmod garante o valor


def prepare_sqlite_file(url: str) -> None:
    """Cria o arquivo do banco com permissão 600 antes do SQLite, que o criaria legível por todos.

    Também corrige bancos criados por versões anteriores. Não mexe na pasta de um caminho customizado
    (FIN_DATABASE_URL): ela pode ser compartilhada com outras coisas.
    """
    database = make_url(url).database
    if not url.startswith("sqlite") or not database or database == ":memory:":
        return
    path = Path(database)
    path.parent.mkdir(mode=PRIVATE_DIR_MODE, parents=True, exist_ok=True)
    with contextlib.suppress(FileExistsError):
        os.close(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, PRIVATE_FILE_MODE))
    path.chmod(PRIVATE_FILE_MODE)

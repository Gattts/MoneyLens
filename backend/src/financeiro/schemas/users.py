import datetime as dt
from typing import Annotated

from pydantic import StringConstraints

from financeiro.schemas.common import InputModel, OutputModel
from financeiro.services.users import UserStatus


class UserOut(OutputModel):
    id: int
    username: str
    is_admin: bool
    status: UserStatus
    invite_expires_at: dt.datetime | None


class UserCreateIn(InputModel):
    username: Annotated[str, StringConstraints(min_length=1, max_length=100)]


class InviteOut(OutputModel):
    user: UserOut
    code: str  # mostrado uma única vez; o banco guarda só o hash


class ActivateIn(InputModel):
    username: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    code: Annotated[str, StringConstraints(min_length=1, max_length=20)]
    # A regra de tamanho (8 a 128) é conferida com a mensagem própria; aqui só barra o absurdo.
    password: Annotated[str, StringConstraints(min_length=1, max_length=200)]

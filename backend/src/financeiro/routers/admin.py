import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select

from financeiro.db import DbSession
from financeiro.errors import conflict
from financeiro.models import User
from financeiro.schemas.common import ItemId
from financeiro.schemas.users import InviteOut, UserCreateIn, UserOut
from financeiro.security import AdminUser, require_admin
from financeiro.services.lookup import get_or_404
from financeiro.services.users import create_pending_user, issue_invite, user_status

router = APIRouter(prefix="/admin/users", tags=["usuários"], dependencies=[Depends(require_admin)])
logger = logging.getLogger(__name__)

NOT_FOUND = "Usuário não encontrado."


def user_out(user: User, now: datetime) -> UserOut:
    return UserOut(
        id=user.id,
        username=user.username,
        is_admin=user.is_admin,
        status=user_status(user, now),
        invite_expires_at=user.invite_expires_at,
    )


@router.get("")
def list_users(session: DbSession) -> list[UserOut]:
    now = datetime.now(UTC)
    return [user_out(user, now) for user in session.scalars(select(User).order_by(User.username_key))]


@router.post("", status_code=201)
def create_user(body: UserCreateIn, session: DbSession) -> InviteOut:
    now = datetime.now(UTC)
    user, code = create_pending_user(session, body.username, now)
    logger.info("Usuário %d criado", user.id)
    return InviteOut(user=user_out(user, now), code=code)


@router.post("/{item_id}/invite")
def new_invite(item_id: ItemId, session: DbSession, admin: AdminUser) -> InviteOut:
    if item_id == admin.id:
        raise conflict("Você não pode gerar um convite para a sua própria conta (use o set-password).")
    user = get_or_404(session, User, item_id, NOT_FOUND)
    now = datetime.now(UTC)
    code = issue_invite(user, now)
    session.commit()
    logger.info("Convite gerado para o usuário %d", user.id)
    return InviteOut(user=user_out(user, now), code=code)


@router.delete("/{item_id}", status_code=204)
def delete_user(item_id: ItemId, session: DbSession, admin: AdminUser) -> None:
    if item_id == admin.id:
        raise conflict("Você não pode excluir a sua própria conta.")
    user = get_or_404(session, User, item_id, NOT_FOUND)
    if user.activated_at is not None:
        raise conflict("Só é possível excluir quem ainda não ativou a conta.")
    session.delete(user)  # o banco apaga junto o pacote padrão (ON DELETE CASCADE)
    session.commit()

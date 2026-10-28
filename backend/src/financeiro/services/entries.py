"""Validação compartilhada por lançamentos e fixas: categoria, grupo do orçamento, cartão e meta."""

from sqlalchemy.orm import Session

from financeiro.domain.enums import Bucket, Kind, PaymentMethod
from financeiro.errors import invalid
from financeiro.models import Category, CreditCard, Goal


def resolve_bucket(
    session: Session,
    *,
    kind: Kind,
    category_id: int,
    bucket: Bucket | None,
    current_category_id: int | None = None,
) -> Bucket | None:
    """Confere a categoria e devolve o grupo do orçamento (o da categoria, se não vier um)."""
    category = session.get(Category, category_id)
    if category is None:
        raise invalid("category_id", "Categoria não encontrada.")
    if category.kind != kind:
        expected = "despesa" if kind is Kind.EXPENSE else "receita"
        raise invalid("category_id", f"Escolha uma categoria de {expected}.")
    if category.archived and category_id != current_category_id:
        raise invalid("category_id", "Esta categoria está arquivada. Escolha outra ou desarquive-a.")
    if kind is Kind.INCOME:
        if bucket is not None:
            raise invalid("bucket", "Receitas não entram nos grupos do orçamento.")
        return None
    return bucket or category.default_bucket


def check_payment(
    session: Session,
    *,
    kind: Kind,
    payment_method: PaymentMethod,
    card_id: int | None,
    current_card_id: int | None = None,
) -> None:
    if payment_method is not PaymentMethod.CREDIT_CARD:
        if card_id is not None:
            raise invalid("card_id", "Informe o cartão só quando a forma de pagamento for cartão de crédito.")
        return
    if kind is Kind.INCOME:
        raise invalid("payment_method", "Receitas não podem ser lançadas no cartão de crédito.")
    if card_id is None:
        raise invalid("card_id", "Escolha o cartão.")
    card = session.get(CreditCard, card_id)
    if card is None:
        raise invalid("card_id", "Cartão não encontrado.")
    if card.archived and card_id != current_card_id:
        raise invalid("card_id", "Este cartão está arquivado. Escolha outro ou desarquive-o.")


def check_goal(
    session: Session,
    *,
    goal_id: int | None,
    bucket: Bucket | None,
    current_goal_id: int | None = None,
) -> None:
    if goal_id is None:
        return
    if bucket is not Bucket.SAVINGS:
        raise invalid("goal_id", "Só lançamentos de poupança podem ser ligados a uma meta.")
    goal = session.get(Goal, goal_id)
    if goal is None:
        raise invalid("goal_id", "Meta não encontrada.")
    if goal.archived and goal_id != current_goal_id:
        raise invalid("goal_id", "Esta meta está arquivada.")

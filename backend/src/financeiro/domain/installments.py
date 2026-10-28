"""Divisão de uma compra parcelada."""

from datetime import date

from financeiro.domain.months import add_months, clamp_day


def split_amount(total_cents: int, count: int) -> list[int]:
    """Divide o total em parcelas que somam exatamente o total e diferem em no máximo 1 centavo.

    As primeiras parcelas recebem os centavos que sobram: 100 em 3 vira [34, 33, 33].
    """
    if count < 1:
        raise ValueError("O número de parcelas precisa ser pelo menos 1.")
    if total_cents < count:
        raise ValueError("O valor é pequeno demais para esse número de parcelas.")
    base, remainder = divmod(total_cents, count)
    return [base + 1 if index < remainder else base for index in range(count)]


def installment_dates(purchase: date, count: int) -> list[date]:
    """Mesmo dia da compra nos meses seguintes, sempre calculado a partir da data original.

    Assim, 31/01 gera 28/02 e depois 31/03, e não 28/03.
    """
    return [clamp_day(add_months(purchase, index), purchase.day) for index in range(count)]

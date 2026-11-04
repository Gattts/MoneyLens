"""Pontuação de uma previsão contra o que aconteceu, com a mesma conta que o app usa."""


def score(
    *, median_cents: float, upper_cents: float, committed_cents: int, target_cents: int, baseline_cents: int
) -> tuple[float, float, bool]:
    """(erro do modelo, erro da estatística, se o máximo provável cobriu o real), comparando totais do mês.

    O modelo prevê só o restante (o que ainda entra depois do dia); como no app, o restante negativo vira
    zero e o provável nunca fica abaixo do comprometido.
    """
    actual = committed_cents + target_cents
    likely = committed_cents + max(0.0, median_cents)
    ceiling = max(committed_cents + max(0.0, upper_cents), likely)
    return abs(likely - actual), abs(baseline_cents - actual), actual <= ceiling

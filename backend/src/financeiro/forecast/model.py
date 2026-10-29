"""Rede que prevê a faixa do total do mês: valor provável (quantil 0,5) e teto (quantil 0,9)."""

import torch
from torch import nn

from financeiro.forecast.features import FEATURE_NAMES

QUANTILES = (0.5, 0.9)
HIDDEN = 32


class QuantileNet(nn.Module):
    def __init__(self, inputs: int = len(FEATURE_NAMES), hidden: int = HIDDEN) -> None:
        super().__init__()
        self.body = nn.Sequential(
            nn.Linear(inputs, hidden), nn.ReLU(), nn.Linear(hidden, hidden), nn.ReLU(), nn.Linear(hidden, 2)
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        out = self.body(features)
        median = out[..., 0]
        upper = median + nn.functional.softplus(out[..., 1])  # o teto nunca fica abaixo do provável
        return torch.stack([median, upper], dim=-1)


def pinball_loss(
    pred: torch.Tensor, target: torch.Tensor, quantiles: tuple[float, ...] = QUANTILES
) -> torch.Tensor:
    """Perda quantílica média: erra para cima e para baixo com pesos diferentes, um por quantil."""
    losses = []
    for index, quantile in enumerate(quantiles):
        error = target - pred[..., index]
        losses.append(torch.maximum(quantile * error, (quantile - 1) * error).mean())
    return torch.stack(losses).mean()

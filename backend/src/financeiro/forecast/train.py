"""Treino do modelo de previsão com PyTorch: pré-treino sintético, ajuste por usuário e exportação ONNX.

Só roda com o grupo `ml` instalado (uv sync --group ml); o app usa o modelo exportado, com onnxruntime.
"""

import copy
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import torch

from financeiro.domain.months import add_months
from financeiro.forecast import BASE_PT
from financeiro.forecast.baseline import baseline_cents
from financeiro.forecast.features import FEATURE_NAMES, Snapshot, history_months, training_snapshots
from financeiro.forecast.history import Expense
from financeiro.forecast.model import QuantileNet, pinball_loss
from financeiro.forecast.synthetic import synthetic_history

SEED = 7
PRETRAIN_LR = 1e-3
FINETUNE_LR = 1e-4
PATIENCE = 20  # épocas sem melhorar na validação antes de parar
MIN_MONTHS = 2
# Tamanho do pré-treino do modelo base (os testes encolhem para rodar rápido).
BASE_PRETRAIN: dict[str, Any] = {"histories": 40, "months": 24, "categories": 12, "epochs": 300}


@dataclass
class TrainResult:
    model: QuantileNet
    metrics: dict[str, float | int]


def as_tensors(snapshots: list[Snapshot]) -> tuple[torch.Tensor, torch.Tensor]:
    """Entradas [N, 7] e alvos [N] (total do mês dividido pela escala)."""
    features = torch.tensor([shot.values for shot in snapshots], dtype=torch.float32)
    targets = torch.tensor(
        [(shot.target_cents or 0) / shot.scale_cents for shot in snapshots], dtype=torch.float32
    )
    return features, targets


def pretrain(
    seed: int = SEED, *, histories: int = 40, months: int = 24, categories: int = 12, epochs: int = 300
) -> QuantileNet:
    """Modelo base: aprende padrões típicos em históricos inventados (sem dado real)."""
    torch.manual_seed(seed)
    end = add_months(date(2025, 1, 1), months)
    snapshots = [
        shot
        for index in range(histories)
        for shot in training_snapshots(synthetic_history(seed + index, months, categories), end)
    ]
    model = QuantileNet()
    _fit(model, *as_tensors(snapshots), epochs=epochs, lr=PRETRAIN_LR)
    return model


def train_base(output_dir: Path, seed: int = SEED) -> None:
    """Gera o modelo base sintético: `base.pt` (pesos) e `base.onnx` (para o app)."""
    model = pretrain(seed, **BASE_PRETRAIN)
    output_dir.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), output_dir / "base.pt")
    (output_dir / "base.onnx").write_bytes(export_onnx(model))


def load_base(path: Path = BASE_PT) -> QuantileNet:
    model = QuantileNet()
    model.load_state_dict(torch.load(path, weights_only=True))
    return model


def split_months(months: list[date]) -> tuple[list[date], date | None, date]:
    """Meses de treino, mês que decide a parada antecipada (se houver) e mês de teste — sempre o último.

    O mês de teste nunca escolhe a parada: senão o erro medido nele favoreceria o modelo contra a estatística.
    Com só 2 meses não há mês para a parada, e o treino roda um número fixo de épocas.
    """
    if len(months) > MIN_MONTHS:
        return months[:-2], months[-2], months[-1]
    return months[:-1], None, months[-1]


def finetune(
    base: QuantileNet, expenses: list[Expense], until_month: date, seed: int = SEED, *, epochs: int = 200
) -> TrainResult:
    """Ajusta o modelo base a uma pessoa: testa no último mês fechado e treina de novo com todos os meses."""
    months = history_months(expenses, until_month)
    if len(months) < MIN_MONTHS:
        raise ValueError(f"São precisos pelo menos {MIN_MONTHS} meses fechados; há {len(months)}.")
    snapshots = training_snapshots(expenses, until_month)
    train_months, stop_month, test_month = split_months(months)
    train = [shot for shot in snapshots if shot.month in train_months]
    stop = [shot for shot in snapshots if shot.month == stop_month]
    test = [shot for shot in snapshots if shot.month == test_month]
    torch.manual_seed(seed)
    trial = copy.deepcopy(base)
    validation = as_tensors(stop) if stop else None
    best_epoch = _fit(trial, *as_tensors(train), epochs=epochs, lr=FINETUNE_LR, validation=validation)
    metrics = _metrics(trial, test, expenses) | {
        "train_examples": len(train),
        "test_examples": len(test),
        "months": len(months),
    }
    torch.manual_seed(seed)
    final = copy.deepcopy(base)
    _fit(final, *as_tensors(snapshots), epochs=max(best_epoch, 1), lr=FINETUNE_LR)
    return TrainResult(final, metrics)


def export_onnx(model: QuantileNet) -> bytes:
    """Entrada `features` float32 [N, 7]; saída `quantiles` [N, 2] (provável e teto, sobre a escala)."""
    model.eval()
    program = torch.onnx.export(
        model,
        (torch.zeros(1, len(FEATURE_NAMES)),),
        input_names=["features"],
        output_names=["quantiles"],
        dynamic_shapes=({0: torch.export.Dim("n")},),
        dynamo=True,
    )
    if program is None:  # com dynamo=True o export devolve o programa; sem ele, não há o que gravar
        raise RuntimeError("A exportação ONNX não devolveu o modelo.")
    return bytes(program.model_proto.SerializeToString())


def _fit(
    model: QuantileNet,
    features: torch.Tensor,
    targets: torch.Tensor,
    *,
    epochs: int,
    lr: float,
    validation: tuple[torch.Tensor, torch.Tensor] | None = None,
) -> int:
    """Treina em lote único; com validação, guarda os pesos da melhor época e devolve quantas épocas usou."""
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    best_loss, best_epoch, best_state = float("inf"), epochs, None
    for epoch in range(1, epochs + 1):
        model.train()
        optimizer.zero_grad()
        loss = pinball_loss(model(features), targets)
        loss.backward()  # type: ignore[no-untyped-call]
        optimizer.step()
        if validation is None:
            continue
        model.eval()
        with torch.no_grad():
            val_loss = pinball_loss(model(validation[0]), validation[1]).item()
        if val_loss < best_loss:
            best_loss, best_epoch, best_state = val_loss, epoch, copy.deepcopy(model.state_dict())
        elif epoch - best_epoch >= PATIENCE:
            break
    if best_state is not None:
        model.load_state_dict(best_state)
    return best_epoch


def _metrics(model: QuantileNet, test: list[Snapshot], expenses: list[Expense]) -> dict[str, float | int]:
    features, _ = as_tensors(test)
    model.eval()
    with torch.no_grad():
        predicted = model(features).numpy()
    model_errors, baseline_errors, covered = [], [], 0
    for shot, (median, upper) in zip(test, predicted, strict=True):
        actual = shot.target_cents or 0
        model_errors.append(abs(median * shot.scale_cents - actual))
        day = date(shot.month.year, shot.month.month, shot.day)
        ahead = sum(
            e.amount_cents
            for e in expenses
            if e.category_id == shot.category_id
            and e.fixed
            and e.date.year == day.year
            and e.date.month == day.month
            and e.date.day > shot.day
        )
        baseline_errors.append(
            abs(baseline_cents(expenses, shot.category_id, shot.month, day, ahead) - actual)
        )
        covered += actual <= upper * shot.scale_cents
    return {
        "mae_model_cents": round(sum(model_errors) / len(model_errors)),
        "mae_baseline_cents": round(sum(baseline_errors) / len(baseline_errors)),
        "coverage_p90": round(covered / len(test), 4),
    }

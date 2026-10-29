from datetime import date

import numpy as np
import onnxruntime
import pytest

torch = pytest.importorskip("torch")

from financeiro.forecast.features import FEATURE_NAMES, training_snapshots  # noqa: E402
from financeiro.forecast.model import QuantileNet, pinball_loss  # noqa: E402
from financeiro.forecast.synthetic import synthetic_history  # noqa: E402
from financeiro.forecast.train import as_tensors, export_onnx, finetune, pretrain  # noqa: E402

SMALL = {"histories": 3, "months": 8, "categories": 4, "epochs": 40}


def test_pinball_loss_matches_a_hand_computed_case():
    loss = pinball_loss(torch.tensor([[1.0, 2.0]]), torch.tensor([3.0]))
    # q=0,5: erro 2 → 1,0; q=0,9: erro 1 → 0,9; média 0,95
    assert loss.item() == pytest.approx(0.95)


def test_upper_quantile_is_never_below_the_median():
    torch.manual_seed(0)
    out = QuantileNet()(torch.randn(256, len(FEATURE_NAMES)) * 5)
    assert bool((out[:, 1] >= out[:, 0]).all())


def test_short_pretraining_beats_predicting_zero():
    model = pretrain(seed=7, **SMALL)
    features, targets = as_tensors(
        training_snapshots(synthetic_history(99, 8, 4), until_month=date(2030, 1, 1))
    )
    with torch.no_grad():
        trained = pinball_loss(model(features), targets).item()
    zeros = pinball_loss(torch.zeros(len(targets), 2), targets).item()
    assert trained < zeros


def test_same_seed_gives_the_same_weights():
    first, second = pretrain(seed=7, **SMALL), pretrain(seed=7, **SMALL)
    for a, b in zip(first.state_dict().values(), second.state_dict().values(), strict=True):
        assert torch.equal(a, b)


def test_onnx_export_matches_pytorch():
    model = pretrain(seed=7, **SMALL)
    features = torch.rand(16, len(FEATURE_NAMES))
    session = onnxruntime.InferenceSession(export_onnx(model))
    (onnx_out,) = session.run(["quantiles"], {"features": features.numpy().astype(np.float32)})
    with torch.no_grad():
        np.testing.assert_allclose(onnx_out, model(features).numpy(), atol=1e-4)


def test_finetune_validates_on_the_last_closed_month():
    base = pretrain(seed=7, **SMALL)
    expenses = synthetic_history(42, 4, 3)
    result = finetune(base, expenses, until_month=date(2030, 1, 1), seed=7, epochs=20)
    metrics = result.metrics
    assert set(metrics) == {
        "mae_model_cents",
        "mae_baseline_cents",
        "coverage_p90",
        "train_examples",
        "test_examples",
        "months",
    }
    assert metrics["months"] == 4
    assert metrics["test_examples"] > 0 and metrics["train_examples"] > metrics["test_examples"]
    assert 0 <= metrics["coverage_p90"] <= 1


def test_finetune_needs_two_closed_months():
    base = pretrain(seed=7, **SMALL)
    with pytest.raises(ValueError, match="2 meses"):
        finetune(base, synthetic_history(42, 1, 3), until_month=date(2030, 1, 1))


def test_split_keeps_the_test_month_out_of_early_stopping():
    from financeiro.forecast.train import split_months  # noqa: PLC0415

    months = [date(2026, m, 1) for m in (6, 7, 8, 9)]
    assert split_months(months) == (months[:2], months[2], months[3])
    assert split_months(months[:2]) == (months[:1], None, months[1])


def test_finetune_never_early_stops_on_the_test_month(monkeypatch):
    from financeiro.forecast import train  # noqa: PLC0415

    base = pretrain(seed=7, **SMALL)
    expenses = synthetic_history(42, 4, 3)
    until = date(2030, 1, 1)
    validations = []
    original = train._fit

    def spy(*args, **kwargs):
        if kwargs.get("validation") is not None:
            validations.append(kwargs["validation"][0])
        return original(*args, **kwargs)

    monkeypatch.setattr(train, "_fit", spy)
    finetune(base, expenses, until_month=until, seed=7, epochs=20)
    shots = training_snapshots(expenses, until)
    months = sorted({shot.month for shot in shots})
    test_features, _ = as_tensors([shot for shot in shots if shot.month == months[-1]])
    stop_features, _ = as_tensors([shot for shot in shots if shot.month == months[-2]])
    assert len(validations) == 1
    assert torch.equal(validations[0], stop_features)
    assert not torch.equal(validations[0], test_features)

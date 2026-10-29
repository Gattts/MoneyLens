"""Previsão do gasto do mês por categoria: medidas, estatística, modelo (PyTorch → ONNX) e previsão."""

import importlib.util
from pathlib import Path

PACKAGE_DIR = Path(__file__).parent
BASE_PT = PACKAGE_DIR / "base.pt"  # pesos do modelo base sintético (ponto de partida do ajuste por usuário)
BASE_ONNX = PACKAGE_DIR / "base.onnx"  # o mesmo modelo, exportado para o app usar com onnxruntime
ML_MISSING = "Instale as dependências de ML: uv sync --group ml"


def ml_available() -> bool:
    """O PyTorch só existe com o grupo `ml`; o app em produção funciona sem ele."""
    return importlib.util.find_spec("torch") is not None

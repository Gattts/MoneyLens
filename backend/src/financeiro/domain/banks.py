"""Nome de exibição dos bancos (o código é o que o leitor grava na importação)."""

BANK_NAMES = {"inter": "Inter", "nubank": "Nubank", "picpay": "PicPay"}


def bank_name(code: str) -> str:
    return BANK_NAMES.get(code, code)

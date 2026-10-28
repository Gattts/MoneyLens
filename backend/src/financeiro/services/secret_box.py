"""Cifra de segredos guardados no banco (a senha do PDF da fatura), com chave derivada do FIN_SECRET_KEY.

Um vazamento do banco sozinho não revela a senha. Trocar o FIN_SECRET_KEY torna as senhas salvas ilegíveis:
`unseal` devolve None e o app volta a pedir a senha.
"""

import base64
import binascii
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

INFO = b"financeiro/invoice-password"
KEY_BYTES = 32
NONCE_BYTES = 12


def _cipher(secret_key: str) -> AESGCM:
    key = HKDF(algorithm=hashes.SHA256(), length=KEY_BYTES, salt=None, info=INFO).derive(secret_key.encode())
    return AESGCM(key)


def seal(plain: str, secret_key: str) -> str:
    nonce = os.urandom(NONCE_BYTES)
    return base64.urlsafe_b64encode(nonce + _cipher(secret_key).encrypt(nonce, plain.encode(), None)).decode()


def unseal(token: str, secret_key: str) -> str | None:
    try:
        raw = base64.urlsafe_b64decode(token.encode())
        plain = _cipher(secret_key).decrypt(raw[:NONCE_BYTES], raw[NONCE_BYTES:], None)
        return plain.decode()
    except (InvalidTag, ValueError, binascii.Error):  # chave trocada, valor adulterado ou lixo
        return None

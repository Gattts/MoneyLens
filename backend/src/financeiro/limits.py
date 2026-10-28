"""Limite de tamanho do corpo das requisições, contra esgotamento de memória."""

import json

from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

TOO_LARGE_MESSAGE = "Requisição grande demais."
HTTP_STATUS_TOO_LARGE = 413


class BodySizeLimitMiddleware:
    """Recusa com 413 corpos maiores que `max_bytes` sem lê-los inteiros na memória.

    Confere o Content-Length declarado e, em envios sem ele (chunked), conta os bytes que chegam.
    """

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        declared = _declared_length(scope)
        if declared is not None and declared > self.max_bytes:
            await _reply_too_large(send)
            return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    # Vira uma resposta 413 no tratador de erros HTTP da aplicação.
                    raise HTTPException(status_code=HTTP_STATUS_TOO_LARGE, detail=TOO_LARGE_MESSAGE)
            return message

        await self.app(scope, limited_receive, send)


def _declared_length(scope: Scope) -> int | None:
    for name, value in scope["headers"]:
        if name == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None


async def _reply_too_large(send: Send) -> None:
    body = json.dumps({"detail": TOO_LARGE_MESSAGE}, ensure_ascii=False).encode()
    await send(
        {
            "type": "http.response.start",
            "status": HTTP_STATUS_TOO_LARGE,
            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
        }
    )
    await send({"type": "http.response.body", "body": body})

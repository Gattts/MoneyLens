"""Erros da aplicação e tradução das mensagens de validação para português.

Toda resposta de erro tem o formato {"detail": "...", "errors": [{"field": ..., "message": ...}]},
para o frontend poder mostrar a mensagem ao lado do campo certo.
"""

import logging
from collections.abc import Mapping, Sequence
from typing import Any, cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("financeiro")

REQUEST_PARTS = {"body", "query", "path", "header", "cookie"}
HTTP_STATUS_NOT_FOUND = 404
HTTP_STATUS_METHOD_NOT_ALLOWED = 405


class AppError(Exception):
    """Erro esperado, com mensagem pronta para mostrar ao usuário."""

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        *,
        field: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.field = field
        self.headers = headers


def invalid(field: str, message: str) -> AppError:
    return AppError(message, 422, field=field)


def not_found(message: str) -> AppError:
    return AppError(message, 404)


def conflict(message: str) -> AppError:
    return AppError(message, 409)


def _field_name(location: tuple[Any, ...]) -> str | None:
    parts = [str(part) for part in location if part not in REQUEST_PARTS]
    return ".".join(parts) or None


_SIMPLE_MESSAGES = {
    "missing": "Campo obrigatório.",
    "int_type": "Informe um número inteiro.",
    "int_parsing": "Informe um número inteiro.",
    "int_from_float": "Informe um número inteiro.",
    "date_type": "Data inválida. Use o formato AAAA-MM-DD.",
    "date_parsing": "Data inválida. Use o formato AAAA-MM-DD.",
    "date_from_datetime_parsing": "Data inválida. Use o formato AAAA-MM-DD.",
    "date_from_datetime_inexact": "Data inválida. Use o formato AAAA-MM-DD.",
    "enum": "Opção inválida.",
    "literal_error": "Opção inválida.",
    "extra_forbidden": "Campo não permitido.",
    "bool_type": "Informe verdadeiro ou falso.",
    "bool_parsing": "Informe verdadeiro ou falso.",
    "string_type": "Informe um texto.",
    "json_invalid": "O corpo da requisição não é um JSON válido.",
    "model_attributes_type": "Formato inválido: envie um objeto JSON.",
    "dict_type": "Formato inválido: envie um objeto JSON.",
}
_TEMPLATE_MESSAGES = {
    "string_too_short": "Use pelo menos {min_length} caracteres.",
    "string_too_long": "Use no máximo {max_length} caracteres.",
    "greater_than": "Informe um valor maior que {gt}.",
    "greater_than_equal": "Informe um valor a partir de {ge}.",
    "less_than_equal": "Informe um valor até {le}.",
}


def _message(error: dict[str, Any]) -> str:
    kind = error["type"]
    context = error.get("ctx") or {}
    if kind == "string_too_short" and context.get("min_length") == 1:
        return "Preencha este campo."
    if kind in _SIMPLE_MESSAGES:
        return _SIMPLE_MESSAGES[kind]
    if kind in _TEMPLATE_MESSAGES:
        return _TEMPLATE_MESSAGES[kind].format(**context)
    # Erros criados pelo próprio código (PydanticCustomError) já vêm com a mensagem em português.
    return str(error.get("msg") or "Valor inválido.")


def _error_response(
    status_code: int,
    detail: str,
    errors: Sequence[Mapping[str, str | None]] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    content: dict[str, Any] = {"detail": detail}
    if errors:
        content["errors"] = [dict(error) for error in errors]
    return JSONResponse(status_code=status_code, content=content, headers=dict(headers) if headers else None)


# O Starlette registra handlers com a assinatura (Request, Exception); cada um recebe só o tipo para o
# qual foi registrado, então o cast apenas informa isso ao verificador de tipos.
async def _handle_app_error(_request: Request, exc: Exception) -> JSONResponse:
    error = cast(AppError, exc)
    errors = [{"field": error.field, "message": error.message}] if error.field else None
    return _error_response(error.status_code, error.message, errors, error.headers)


async def _handle_validation_error(_request: Request, exc: Exception) -> JSONResponse:
    details = cast(RequestValidationError, exc).errors()
    errors = [{"field": _field_name(tuple(err["loc"])), "message": _message(err)} for err in details]
    return _error_response(422, "Verifique os campos informados.", errors)


async def _handle_integrity_error(_request: Request, exc: Exception) -> JSONResponse:
    # Só a 1ª linha da mensagem do banco (qual restrição falhou). O SQL completo, e o "DETAIL" do
    # Postgres, trariam os valores digitados.
    summary = str(cast(IntegrityError, exc).orig).splitlines()[0]
    logger.warning("Violação de integridade no banco: %s", summary)
    return _error_response(409, "A operação conflita com dados já cadastrados.")


async def _handle_http_error(_request: Request, exc: Exception) -> JSONResponse:
    error = cast(StarletteHTTPException, exc)
    messages = {
        HTTP_STATUS_NOT_FOUND: "Recurso não encontrado.",
        HTTP_STATUS_METHOD_NOT_ALLOWED: "Método não permitido.",
    }
    detail = messages.get(error.status_code, str(error.detail))
    return _error_response(error.status_code, detail, headers=error.headers)


async def _handle_unexpected_error(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Erro inesperado", exc_info=exc)
    return _error_response(500, "Erro inesperado no servidor. Tente novamente.")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(IntegrityError, _handle_integrity_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_error)
    app.add_exception_handler(Exception, _handle_unexpected_error)

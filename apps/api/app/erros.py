"""Erros no formato RFC 7807 (`application/problem+json`)."""

import logging
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)
MEDIA_TYPE = "application/problem+json"


class Problema(Exception):
    def __init__(self, status: int, detalhe: str | None = None, titulo: str | None = None):
        self.status = status
        self.detalhe = detalhe
        self.titulo = titulo or HTTPStatus(status).phrase


def resposta_problema(
    request: Request, status: int, titulo: str, detalhe: str | None = None, **extras
) -> JSONResponse:
    corpo = {
        "type": "about:blank",
        "title": titulo,
        "status": status,
        "instance": request.url.path,
    }
    if detalhe:
        corpo["detail"] = detalhe
    corpo.update(extras)
    headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
    return JSONResponse(corpo, status_code=status, media_type=MEDIA_TYPE, headers=headers)


def registrar_handlers(app: FastAPI) -> None:
    @app.exception_handler(Problema)
    async def _problema(request: Request, exc: Problema):
        return resposta_problema(request, exc.status, exc.titulo, exc.detalhe)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        titulo = HTTPStatus(exc.status_code).phrase
        detalhe = exc.detail if isinstance(exc.detail, str) and exc.detail != titulo else None
        return resposta_problema(request, exc.status_code, titulo, detalhe)

    @app.exception_handler(RequestValidationError)
    async def _validacao(request: Request, exc: RequestValidationError):
        erros = [
            {"campo": ".".join(str(p) for p in e["loc"][1:]), "mensagem": e["msg"]}
            for e in exc.errors()
        ]
        return resposta_problema(
            request, 422, "Unprocessable Entity", "Parâmetros inválidos", erros=erros
        )

    @app.exception_handler(Exception)
    async def _inesperado(request: Request, exc: Exception):
        log.exception("erro não tratado em %s", request.url.path)
        return resposta_problema(request, 500, "Internal Server Error")

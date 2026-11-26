"""API do analisebolsa. Só a web acessa: na Vercel, com a chave em X-Internal-Key."""

import hmac
import logging

from fastapi import Depends, FastAPI, Request

from app import schemas as s
from app.config import get_settings
from app.deps import usuario_opcional
from app.erros import registrar_handlers, resposta_problema
from app.rotas import (
    admin,
    alertas,
    ativos,
    backtest,
    carteiras,
    conta,
    health,
    indices,
    mercado,
    posicao,
    screener,
    simulador,
    watchlist,
)

ERROS = {
    code: {"model": s.Problema, "content": {"application/problem+json": {}}}
    for code in (401, 403, 404, 409, 422)
}


def create_app() -> FastAPI:
    app = FastAPI(
        title="analisebolsa API",
        version="0.1.0",
        description="Conteúdo educacional. Não é recomendação de investimento.",
        responses=ERROS,
        # Um token presente e inválido é rejeitado em qualquer rota, inclusive nas públicas.
        dependencies=[Depends(usuario_opcional)],
    )
    registrar_handlers(app)

    @app.middleware("http")
    async def exigir_chave_interna(request: Request, call_next):
        chave = get_settings().internal_api_key
        if chave and request.url.path != "/v1/health":
            enviada = request.headers.get("x-internal-key", "")
            if not hmac.compare_digest(enviada.encode(), chave.encode()):
                return resposta_problema(request, 401, "Unauthorized", "chave interna inválida")
        return await call_next(request)

    rotas = (
        health,
        ativos,
        mercado,
        indices,
        screener,
        simulador,
        backtest,
        posicao,
        watchlist,
        carteiras,
        alertas,
        conta,
        admin,
    )
    for r in (m.router for m in rotas):
        app.include_router(r, prefix="/v1")
    return app


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
app = create_app()

"""API interna do analisebolsa. Só a web acessa (rede interna do Coolify)."""

import logging

from fastapi import Depends, FastAPI

from app import schemas as s
from app.deps import usuario_opcional
from app.erros import registrar_handlers
from app.rotas import admin, ativos, health, mercado

ERROS = {
    code: {"model": s.Problema, "content": {"application/problem+json": {}}}
    for code in (401, 403, 404, 422)
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
    for r in (health.router, ativos.router, mercado.router, admin.router):
        app.include_router(r, prefix="/v1")
    return app


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
app = create_app()

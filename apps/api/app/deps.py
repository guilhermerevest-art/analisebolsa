"""Dependências: conexão com o banco e autenticação por JWT interno."""

import re
import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, Path, Request
from sqlalchemy import Connection

from app.config import get_settings
from app.db import get_engine
from app.erros import Problema

VALIDADE_MAXIMA_S = 60
FOLGA_RELOGIO_S = 5
REGEX_TICKER = re.compile(r"^[A-Z0-9]{4,6}$")


def get_conn() -> Iterator[Connection]:
    with get_engine().connect() as conn:
        yield conn


Conn = Annotated[Connection, Depends(get_conn)]


def ticker_valido(
    ticker: Annotated[str, Path(description="Código de negociação, ex.: PETR4")],
) -> str:
    normalizado = ticker.strip().upper()
    if not REGEX_TICKER.match(normalizado):
        raise Problema(422, f"ticker inválido: {ticker!r}")
    return normalizado


Ticker = Annotated[str, Depends(ticker_valido)]


@dataclass(frozen=True)
class Usuario:
    id: str
    plano: str
    role: str

    @property
    def admin(self) -> bool:
        return self.role == "admin"


def decodificar_token(token: str, segredo: str, agora: float | None = None) -> Usuario:
    """Valida um JWT HS256 com `exp` no máximo 60 s à frente (spec, seção 5)."""
    if not segredo:
        raise Problema(401, "autenticação interna não configurada")
    agora = time.time() if agora is None else agora
    try:
        claims = jwt.decode(
            token,
            segredo,
            algorithms=["HS256"],
            options={"require": ["exp", "sub"], "verify_exp": False},
        )
    except jwt.PyJWTError as e:
        raise Problema(401, "token inválido") from e
    exp = claims["exp"]
    if not isinstance(exp, int | float) or exp < agora - FOLGA_RELOGIO_S:
        raise Problema(401, "token expirado")
    if exp - agora > VALIDADE_MAXIMA_S + FOLGA_RELOGIO_S:
        raise Problema(401, "token com validade acima de 60 s")
    return Usuario(
        id=str(claims["sub"]),
        plano=str(claims.get("plano", "free")),
        role=str(claims.get("role", "user")),
    )


def usuario_opcional(request: Request) -> Usuario | None:
    cabecalho = request.headers.get("Authorization", "")
    if not cabecalho:
        return None
    esquema, _, token = cabecalho.partition(" ")
    if esquema.lower() != "bearer" or not token:
        raise Problema(401, "cabeçalho Authorization deve ser 'Bearer <token>'")
    return decodificar_token(token, get_settings().internal_jwt_secret)


def usuario_obrigatorio(
    usuario: Annotated[Usuario | None, Depends(usuario_opcional)],
) -> Usuario:
    if usuario is None:
        raise Problema(401, "autenticação necessária")
    return usuario


def exigir_admin(usuario: Annotated[Usuario, Depends(usuario_obrigatorio)]) -> Usuario:
    if not usuario.admin:
        raise Problema(403, "acesso restrito a administradores")
    return usuario

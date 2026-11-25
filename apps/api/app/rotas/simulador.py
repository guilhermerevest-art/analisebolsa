from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, Response

from app import schemas as s
from app import simulador as servico
from app.deps import Conn, ticker_valido
from app.erros import Problema

router = APIRouter(prefix="/simulador", tags=["simulador"])
INICIO_MINIMO = date(2005, 1, 1)


@router.get("", response_model=s.Simulacao, summary="Aportes mensais no histórico, CDI e IPCA")
def simular(
    conn: Conn,
    response: Response,
    inicio: date,
    ticker: Annotated[str | None, Query(max_length=6)] = None,
    aporte_inicial: Annotated[float, Query(ge=0, le=1e9)] = 0,
    aporte_mensal: Annotated[float, Query(ge=0, le=1e8)] = 0,
    reinvestir: bool = True,
):
    if aporte_inicial <= 0 and aporte_mensal <= 0:
        raise Problema(422, "informe um aporte inicial ou mensal maior que zero")
    if not INICIO_MINIMO <= inicio < date.today():
        raise Problema(422, f"inicio deve estar entre {INICIO_MINIMO:%d/%m/%Y} e ontem")
    ticker = ticker_valido(ticker) if ticker else None
    response.headers["Cache-Control"] = "public, max-age=3600"
    return servico.simular(conn, ticker, inicio, aporte_inicial, aporte_mensal, reinvestir)

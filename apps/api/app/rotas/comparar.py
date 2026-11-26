from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Query, Response

from app import comparar as cp
from app import schemas as s
from app.deps import Conn

router = APIRouter(prefix="/comparar", tags=["mercado"])


@router.get("", response_model=s.Comparacao, summary="Compara de 2 a 4 ativos")
def comparar(
    conn: Conn,
    response: Response,
    tickers: Annotated[str, Query(description="Separados por vírgula, ex.: PETR4,VALE3")],
    inicio: Annotated[date | None, Query()] = None,
):
    response.headers["Cache-Control"] = "public, max-age=3600"
    return cp.comparar(conn, tickers.split(","), inicio or date.today() - timedelta(days=365))

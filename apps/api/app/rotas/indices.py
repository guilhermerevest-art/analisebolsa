from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Query

from app import schemas as s
from app import usuario as u
from app.deps import Conn
from app.erros import Problema

router = APIRouter(prefix="/indices", tags=["mercado"])
UNIDADES = {"cdi": "pct_dia", "ipca": "pct_mes", "ibov": "pontos"}


@router.get("/{serie}", response_model=s.Indice, summary="Série de CDI, IPCA ou Ibovespa")
def serie(
    conn: Conn,
    serie: s.SerieIndice,
    inicio: Annotated[date | None, Query()] = None,
    fim: Annotated[date | None, Query()] = None,
):
    fim = fim or date.today()
    inicio = inicio or fim - timedelta(days=365)
    if inicio > fim:
        raise Problema(422, "inicio deve ser anterior ou igual a fim")
    return {
        "serie": serie,
        "unidade": UNIDADES[serie],
        "pontos": u.serie_indice(conn, serie, inicio, fim),
    }

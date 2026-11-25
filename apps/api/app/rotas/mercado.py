from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Query

from app import consultas as q
from app import schemas as s
from app.deps import Conn

router = APIRouter(prefix="/mercado", tags=["mercado"])


@router.get(
    "/destaques", response_model=s.Destaques, summary="Maiores altas e baixas do último pregão"
)
def destaques(
    conn: Conn,
    limite: Annotated[int, Query(ge=1, le=50)] = 10,
    volume_minimo: Annotated[
        Decimal,
        Query(ge=0, description="Volume financeiro mínimo em R$, para excluir ativos ilíquidos"),
    ] = Decimal(1_000_000),
):
    data, altas, baixas = q.destaques(conn, limite, volume_minimo)
    return {"data": data, "altas": altas, "baixas": baixas}

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app import consultas as q
from app import schemas as s
from app.deps import Conn, exigir_admin

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(exigir_admin)])


@router.get("/execucoes", response_model=s.Execucoes, summary="Histórico do job")
def execucoes(conn: Conn, limite: Annotated[int, Query(ge=1, le=200)] = 50):
    return {"itens": q.execucoes(conn, limite)}

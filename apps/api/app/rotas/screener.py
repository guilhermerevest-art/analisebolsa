from typing import Annotated, get_args

from fastapi import APIRouter, Query
from pydantic import ConfigDict, Field, create_model

from app import schemas as s
from app import screener as sc
from app.deps import Conn

router = APIRouter(prefix="/screener", tags=["screener"])

_ORDEM = "^-?(" + "|".join(sc.ORDENAVEIS) + ")$"

# Modelo dos query params: cada campo numérico vira `<campo>_min` e `<campo>_max`.
# `extra="forbid"` faz um filtro fora da lista responder 422 em vez de ser ignorado.
FiltrosScreener = create_model(
    "FiltrosScreener",
    __config__=ConfigDict(extra="forbid"),
    tipo=(list[s.TipoAtivo] | None, None),
    setor=(Annotated[str | None, Field(max_length=80)], None),
    tendencia=(s.Tendencia | None, None),
    ordem=(Annotated[str, Field(pattern=_ORDEM)], "-volume_financeiro_20d"),
    pagina=(Annotated[int, Field(ge=1)], 1),
    limite=(Annotated[int, Field(ge=1, le=100)], 50),
    **{f"{c}_{lado}": (float | None, None) for c in sc.NOMES for lado in ("min", "max")},
)


@router.get("", response_model=s.PaginaScreener, summary="Ativos que passam nos filtros")
def screener(conn: Conn, filtros: Annotated[FiltrosScreener, Query()]):
    f = filtros.model_dump()
    faixas = {
        c: (f[f"{c}_min"], f[f"{c}_max"])
        for c in sc.NOMES
        if f[f"{c}_min"] is not None or f[f"{c}_max"] is not None
    }
    itens, total = sc.buscar(
        conn, faixas, f["tipo"], f["setor"], f["tendencia"], f["ordem"], f["pagina"], f["limite"]
    )
    return {"itens": itens, "pagina": f["pagina"], "limite": f["limite"], "total": total}


@router.get("/campos", response_model=s.CamposScreener, summary="Metadados dos filtros")
def campos(conn: Conn):
    faixas = sc.faixas_observadas(conn)
    return {
        "campos": [
            {**c.__dict__, "min": faixas[c.campo][0], "max": faixas[c.campo][1]} for c in sc.CAMPOS
        ],
        "setores": sc.setores(conn),
        "tipos": list(get_args(s.TipoAtivo)),
    }

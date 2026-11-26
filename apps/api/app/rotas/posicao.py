from typing import Annotated

from fastapi import APIRouter, Query, Response
from sqlalchemy import text

from app import consultas as q
from app import schemas as s
from app.deps import Conn, ticker_valido
from app.erros import Problema
from dominio import posicao as ps

router = APIRouter(prefix="/posicao", tags=["posicao"])

AVISO = (
    "Conta de risco com os números informados: não diz o que operar. O stop pode ser "
    "executado abaixo do preço definido em dias de abertura com salto. Não é recomendação "
    "de investimento."
)


@router.get("", response_model=s.Posicao, summary="Tamanho de posição pelo risco até o stop")
def posicao(
    conn: Conn,
    response: Response,
    capital: Annotated[float, Query(gt=0, le=1e10)],
    risco: Annotated[float, Query(ge=0.1, le=5, description="% do capital até o stop")] = 1,
    entrada: Annotated[float | None, Query(gt=0, le=1e6)] = None,
    stop: Annotated[float | None, Query(gt=0, le=1e6)] = None,
    ticker: Annotated[str | None, Query(max_length=6)] = None,
    atr_mult: Annotated[float | None, Query(ge=0.5, le=5, description="Stop em ATR14")] = None,
    lote: Annotated[int, Query(description="1 (fracionário) ou 100 (lote padrão)")] = 100,
    concentracao: Annotated[float, Query(ge=1, le=100, description="% máximo")] = 25,
):
    if lote not in (1, 100):
        raise Problema(422, "lote deve ser 1 ou 100")
    ativo = None
    if ticker:
        t = ticker_valido(ticker)
        a = q.ativo_por_ticker(conn, t)
        linha = conn.execute(
            text(
                """
                SELECT c.data, c.fechamento, i.atr14
                FROM cotacoes_diarias c
                LEFT JOIN indicadores_diarios i USING (ativo_id, data)
                WHERE c.ativo_id = :a ORDER BY c.data DESC LIMIT 1
                """
            ),
            {"a": a["ativo_id"]},
        ).one_or_none()
        if linha is not None:
            ativo = {
                "ticker": t,
                "data": linha.data,
                "fechamento": float(linha.fechamento),
                "atr14": float(linha.atr14) if linha.atr14 is not None else None,
            }
    if entrada is None:
        if ativo is None:
            raise Problema(422, "informe o preço de entrada ou um ativo com cotação")
        entrada = ativo["fechamento"]
    if stop is None:
        if atr_mult is None or ativo is None or ativo["atr14"] is None:
            raise Problema(422, "informe o stop, ou um ativo e o múltiplo do ATR")
        stop = ps.stop_por_atr(entrada, ativo["atr14"], atr_mult)
    try:
        p = ps.calcular(capital, risco, entrada, stop, lote, concentracao)
    except ps.PosicaoInvalida as e:
        raise Problema(422, str(e)) from e
    response.headers["Cache-Control"] = "public, max-age=3600"
    return {
        "capital": capital,
        "risco": risco,
        "entrada": entrada,
        "stop": stop,
        "lote": lote,
        "concentracao": concentracao,
        "ativo": ativo,
        "quantidade": p.quantidade,
        "valor": p.valor,
        "pct_capital": p.pct_capital,
        "distancia_stop": p.distancia_stop,
        "perda_stop": p.perda_stop,
        "perda_pct_capital": p.perda_pct_capital,
        "risco_maximo": p.risco_maximo,
        "limitada_por": p.limitada_por,
        "alvos": [{"multiplo": m, "preco": v} for m, v in p.alvos],
        "aviso": AVISO,
    }

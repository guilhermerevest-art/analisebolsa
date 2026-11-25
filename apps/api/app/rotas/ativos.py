from datetime import date, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app import consultas as q
from app import schemas as s
from app.deps import Conn, Ticker
from app.erros import Problema
from dominio.insights import elegibilidade

router = APIRouter(prefix="/ativos", tags=["ativos"])


def _periodo(inicio: date | None, fim: date | None, padrao_dias: int) -> tuple[date, date]:
    fim = fim or date.today()
    inicio = inicio or fim - timedelta(days=padrao_dias)
    if inicio > fim:
        raise Problema(422, "inicio deve ser anterior ou igual a fim")
    return inicio, fim


@router.get("", response_model=s.PaginaAtivos, summary="Busca por ticker (prefixo) e nome")
def listar(
    conn: Conn,
    busca: Annotated[str | None, Query(max_length=60)] = None,
    tipo: s.TipoAtivo | None = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    limite: Annotated[int, Query(ge=1, le=100)] = 20,
):
    itens, total = q.buscar_ativos(conn, busca, tipo, pagina, limite)
    return {"itens": itens, "pagina": pagina, "limite": limite, "total": total}


@router.get(
    "/{ticker}", response_model=s.AtivoDetalhe, summary="Cadastro, última cotação e variações"
)
def detalhe(conn: Conn, ticker: Ticker):
    ativo = q.ativo_por_ticker(conn, ticker)
    ultima, variacoes = q.ultima_e_variacoes(conn, ativo["ativo_id"])
    return {**ativo, "ultima_cotacao": ultima, "variacoes": variacoes}


@router.get(
    "/{ticker}/cotacoes", response_model=s.Cotacoes, summary="Candles diários, semanais ou mensais"
)
def cotacoes(
    conn: Conn,
    ticker: Ticker,
    inicio: date | None = None,
    fim: date | None = None,
    periodo: Literal["1d", "1w", "1M"] = "1d",
):
    ativo = q.ativo_por_ticker(conn, ticker)
    inicio, fim = _periodo(inicio, fim, 365)
    candles = q.cotacoes(conn, ativo["ativo_id"], inicio, fim, periodo)
    return {"ticker": ticker, "periodo": periodo, "candles": candles}


@router.get("/{ticker}/indicadores", response_model=s.Indicadores, summary="Série dos indicadores")
def indicadores(conn: Conn, ticker: Ticker, inicio: date | None = None, fim: date | None = None):
    ativo = q.ativo_por_ticker(conn, ticker)
    inicio, fim = _periodo(inicio, fim, 365)
    return {"ticker": ticker, "itens": q.indicadores(conn, ativo["ativo_id"], inicio, fim)}


@router.get(
    "/{ticker}/fundamentos", response_model=s.Fundamentos, summary="Último snapshot e histórico"
)
def fundamentos(conn: Conn, ticker: Ticker):
    ativo = q.ativo_por_ticker(conn, ticker)
    historico = q.fundamentos(conn, ativo["ativo_id"])
    return {"ticker": ticker, "ultimo": historico[0] if historico else None, "historico": historico}


@router.get("/{ticker}/proventos", response_model=s.Proventos, summary="Proventos e DY por ano")
def proventos(conn: Conn, ticker: Ticker):
    ativo = q.ativo_por_ticker(conn, ticker)
    itens, dy = q.proventos(conn, ativo["ativo_id"])
    return {"ticker": ticker, "itens": itens, "dy_por_ano": dy}


@router.get(
    "/{ticker}/analise",
    response_model=s.AnaliseAtivo,
    summary="Métricas, insights e cenários do último pregão",
)
def analise(conn: Conn, ticker: Ticker):
    ativo = q.ativo_por_ticker(conn, ticker)
    metricas, insights, cenario = q.analise(conn, ativo["ativo_id"])
    if metricas is None:
        motivo = "Ainda não há análise calculada para este ativo."
        return {"ticker": ticker, "elegivel": False, "motivo": motivo, "metricas": None,
                "insights": [], "cenario": None}  # fmt: skip
    elegivel, motivo = elegibilidade(metricas["pregoes"], metricas["volume_financeiro_20d"])
    return {
        "ticker": ticker,
        "elegivel": elegivel,
        "motivo": motivo,
        "metricas": metricas,
        "insights": insights,
        "cenario": cenario if elegivel else None,
    }

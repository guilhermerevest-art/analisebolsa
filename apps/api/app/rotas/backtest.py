from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response

from app import backtest as servico
from app import schemas as s
from app.deps import Conn, ticker_valido
from app.erros import Problema
from dominio import backtest as bt

router = APIRouter(prefix="/backtest", tags=["backtest"])
INICIO_MINIMO = date(2005, 1, 1)
Inteiro = Annotated[int | None, Query(ge=1, le=1000)]


@router.get("", response_model=s.Backtest, summary="Estratégia por regras no histórico de um ativo")
def backtest(
    conn: Conn,
    response: Response,
    ticker: Annotated[str, Query(max_length=6)],
    estrategia: Literal[
        "cruzamento_mm", "rsi", "macd", "bollinger", "setup_91", "rompimento", "buy_and_hold"
    ],
    inicio: date,
    fim: date | None = None,
    curta: Inteiro = None,
    longa: Inteiro = None,
    rsi_periodo: Inteiro = None,
    rsi_entrada: Inteiro = None,
    rsi_saida: Inteiro = None,
    n_entrada: Inteiro = None,
    n_saida: Inteiro = None,
    macd_rapida: Inteiro = None,
    macd_lenta: Inteiro = None,
    macd_sinal: Inteiro = None,
    bb_periodo: Inteiro = None,
    bb_desvios: Inteiro = None,
    mme_periodo: Inteiro = None,
    stop_atr: Annotated[float | None, Query(ge=1, le=5, description="Múltiplo do ATR14")] = None,
    capital: Annotated[float, Query(ge=1000, le=1e9)] = 10_000,
    corretagem: Annotated[float, Query(ge=0, le=100, description="R$ por execução")] = 0,
    taxas: Annotated[float, Query(ge=0, le=1, description="% do volume")] = 0.03,
    deslizamento: Annotated[float, Query(ge=0, le=2, description="% do preço")] = 0.05,
    cdi_no_caixa: bool = True,
):
    hoje = date.today()
    fim = fim or hoje
    if not INICIO_MINIMO <= inicio < fim <= hoje:
        raise Problema(422, f"o período deve ficar entre {INICIO_MINIMO:%d/%m/%Y} e hoje")
    ticker = ticker_valido(ticker)
    parametros = {
        "curta": curta,
        "longa": longa,
        "rsi_periodo": rsi_periodo,
        "rsi_entrada": rsi_entrada,
        "rsi_saida": rsi_saida,
        "n_entrada": n_entrada,
        "n_saida": n_saida,
        "macd_rapida": macd_rapida,
        "macd_lenta": macd_lenta,
        "macd_sinal": macd_sinal,
        "bb_periodo": bb_periodo,
        "bb_desvios": bb_desvios,
        "mme_periodo": mme_periodo,
    }
    config = bt.Config(
        estrategia,
        parametros,  # type: ignore[arg-type] (validar preenche os padrões)
        stop_atr=stop_atr,
        custos=bt.Custos(corretagem, taxas / 100, deslizamento / 100),
        capital=capital,
        cdi_no_caixa=cdi_no_caixa,
    )
    response.headers["Cache-Control"] = "public, max-age=3600"
    return servico.rodar(conn, ticker, inicio, fim, config)

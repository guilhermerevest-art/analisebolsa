"""Métricas por ativo para o screener e os insights (Fase 2, seção 3.1 da spec).

Funções puras sobre pandas. Percentuais saem em pontos percentuais (12.5 = 12,5%).
Variações e volatilidade usam o `fechamento_ajustado` (retorno total); máxima e
mínima de 52 semanas usam os preços do gráfico (`maxima`/`minima`).
"""

import math
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from decimal import Decimal

import numpy as np
import pandas as pd

PREGOES_ANO = 252
JANELAS_VARIACAO = {"var_1m": 30, "var_3m": 91, "var_6m": 182, "var_12m": 365}
# Histórico que o cálculo precisa: 12 meses de variação e MM200 subindo há 20 pregões.
JANELA_DIAS = 400
CAMPOS_FUNDAMENTOS = ("pl", "pvp", "dy_12m", "roe", "margem_liquida", "div_liq_ebitda")


@dataclass(frozen=True, slots=True)
class Metricas:
    data: date
    preco: Decimal
    pregoes: int
    var_1d: float | None = None
    var_1m: float | None = None
    var_3m: float | None = None
    var_6m: float | None = None
    var_12m: float | None = None
    var_ano: float | None = None
    volatilidade_12m: float | None = None
    drawdown_12m: float | None = None
    max_52s: Decimal | None = None
    min_52s: Decimal | None = None
    pos_52s: float | None = None
    dist_mm50: float | None = None
    dist_mm200: float | None = None
    rsi14: float | None = None
    tendencia: str | None = None
    volume_financeiro_20d: Decimal | None = None
    pl: float | None = None
    pvp: float | None = None
    dy_12m: float | None = None
    roe: float | None = None
    margem_liquida: float | None = None
    div_liq_ebitda: float | None = None
    valor_mercado: Decimal | None = None

    def como_dict(self) -> dict:
        return asdict(self)


def _num(v) -> float | None:
    if v is None:
        return None
    f = float(v)
    return None if math.isnan(f) or math.isinf(f) else f


def _pct(v: float | None, casas: int = 2) -> float | None:
    return None if v is None else round(v * 100, casas)


def _valor_em(serie: pd.Series, limite: date) -> float | None:
    """Último valor com data <= limite (o pregão de referência de uma janela)."""
    anteriores = serie[serie.index <= limite]
    return None if anteriores.empty else _num(anteriores.iloc[-1])


def _variacao(atual: float, base: float | None) -> float | None:
    return None if not base else _pct(atual / base - 1)


def classificar_tendencia(preco: float, mm50: float | None, mm200: pd.Series) -> str | None:
    """Versão objetiva do framework do `technical-analyst`: alinhamento de preço e médias
    e inclinação da MM200 nos últimos 20 pregões."""
    validos = mm200.dropna()
    if mm50 is None or len(validos) < 21:
        return None
    atual, antes = float(validos.iloc[-1]), float(validos.iloc[-21])
    if preco > mm50 > atual and atual > antes:
        return "alta"
    if preco < mm50 < atual and atual < antes:
        return "baixa"
    return "lateral"


def calcular_metricas(
    cotacoes: pd.DataFrame,
    indicadores: pd.DataFrame,
    fundamentos: dict | None = None,
    pregoes: int | None = None,
) -> Metricas | None:
    """`cotacoes`: colunas maxima, minima, fechamento, fechamento_ajustado e volume,
    indexadas por data crescente (pelo menos os últimos `JANELA_DIAS`). `indicadores`:
    mm50, mm200 e rsi14 no mesmo índice. `pregoes`: total do histórico, se a série
    recebida for só a janela recente."""
    if cotacoes.empty:
        return None
    ajust = cotacoes["fechamento_ajustado"].astype(float)
    fech = cotacoes["fechamento"].astype(float)
    hoje: date = cotacoes.index[-1]
    preco = float(fech.iloc[-1])
    atual_aj = float(ajust.iloc[-1])

    variacoes = {
        nome: _variacao(atual_aj, _valor_em(ajust, hoje - timedelta(days=dias)))
        for nome, dias in JANELAS_VARIACAO.items()
    }
    # Uma janela só vale se a série cobre o período inteiro.
    for nome, dias in JANELAS_VARIACAO.items():
        if cotacoes.index[0] > hoje - timedelta(days=dias):
            variacoes[nome] = None
    var_1d = _variacao(atual_aj, _num(ajust.iloc[-2])) if len(ajust) > 1 else None
    fim_ano_anterior = date(hoje.year - 1, 12, 31)
    var_ano = (
        _variacao(atual_aj, _valor_em(ajust, fim_ano_anterior))
        if cotacoes.index[0] <= fim_ano_anterior
        else None
    )

    ultimo_ano = ajust[ajust.index > hoje - timedelta(days=365)]
    retornos = np.log(ultimo_ano / ultimo_ano.shift(1)).dropna()
    volatilidade = (
        _pct(float(retornos.std(ddof=1)) * math.sqrt(PREGOES_ANO)) if len(retornos) >= 60 else None
    )
    drawdown = (
        _pct(float((ultimo_ano / ultimo_ano.cummax() - 1).min())) if len(ultimo_ano) else None
    )

    janela_52s = cotacoes[cotacoes.index > hoje - timedelta(days=365)]
    maximo = Decimal(str(janela_52s["maxima"].max()))
    minimo = Decimal(str(janela_52s["minima"].min()))
    amplitude = float(maximo - minimo)
    pos_52s = round((preco - float(minimo)) / amplitude * 100, 2) if amplitude > 0 else None

    ind = indicadores.reindex(cotacoes.index)
    mm50 = _num(ind["mm50"].iloc[-1]) if "mm50" in ind else None
    mm200 = _num(ind["mm200"].iloc[-1]) if "mm200" in ind else None
    rsi = _num(ind["rsi14"].iloc[-1]) if "rsi14" in ind else None

    financeiro = (fech * cotacoes["volume"].astype(float)).tail(20)
    volume_fin = Decimal(str(round(float(financeiro.mean()), 2))) if len(financeiro) == 20 else None

    f = fundamentos or {}
    return Metricas(
        data=hoje,
        preco=Decimal(str(cotacoes["fechamento"].iloc[-1])),
        pregoes=pregoes if pregoes is not None else len(cotacoes),
        var_1d=var_1d,
        var_ano=var_ano,
        **variacoes,
        volatilidade_12m=volatilidade,
        drawdown_12m=drawdown,
        max_52s=maximo,
        min_52s=minimo,
        pos_52s=pos_52s,
        dist_mm50=_variacao(preco, mm50),
        dist_mm200=_variacao(preco, mm200),
        rsi14=None if rsi is None else round(rsi, 2),
        tendencia=classificar_tendencia(preco, mm50, ind["mm200"]) if "mm200" in ind else None,
        volume_financeiro_20d=volume_fin,
        **{c: _num(f.get(c)) for c in CAMPOS_FUNDAMENTOS},
        valor_mercado=f.get("valor_mercado"),
    )

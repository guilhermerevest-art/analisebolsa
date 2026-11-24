"""Indicadores técnicos em pandas puro (seção 4, etapa 5 da spec).

Convenções, iguais às de StockCharts/TradingView:
- MME começa no índice n-1 com a média simples dos n primeiros valores.
- RSI e ATR usam a suavização de Wilder, semeada com a média simples.
- Bandas de Bollinger usam desvio-padrão populacional (ddof=0).
"""

import numpy as np
import pandas as pd

COLUNAS = [
    "mm20", "mm50", "mm200", "mme9", "rsi14", "macd", "macd_sinal", "macd_hist",
    "bb_superior", "bb_inferior", "atr14", "vol_media20",
]  # fmt: skip

# Janela de dias corridos antes do primeiro pregão novo que garante a MM200.
JANELA_AQUECIMENTO_DIAS = 400


def mm(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def _suavizar(valores: np.ndarray, n: int, alpha: float) -> np.ndarray:
    """Média recursiva semeada pela média simples dos n primeiros valores
    não nulos. `alpha` = 2/(n+1) para MME e 1/n para Wilder."""
    saida = np.full(len(valores), np.nan)
    validos = np.flatnonzero(~np.isnan(valores))
    if len(validos) < n:
        return saida
    inicio = validos[0]
    semente = inicio + n - 1
    if np.isnan(valores[inicio : semente + 1]).any():
        return saida
    saida[semente] = valores[inicio : semente + 1].mean()
    for i in range(semente + 1, len(valores)):
        saida[i] = saida[i - 1] + alpha * (valores[i] - saida[i - 1])
    return saida


def mme(s: pd.Series, n: int) -> pd.Series:
    return pd.Series(_suavizar(s.to_numpy(float), n, 2 / (n + 1)), index=s.index)


def wilder(s: pd.Series, n: int) -> pd.Series:
    return pd.Series(_suavizar(s.to_numpy(float), n, 1 / n), index=s.index)


def rsi(fechamento: pd.Series, n: int = 14) -> pd.Series:
    delta = fechamento.diff()
    ganho = wilder(delta.clip(lower=0), n)
    perda = wilder((-delta).clip(lower=0), n)
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = ganho / perda
        valor = 100 - 100 / (1 + rs)
    valor = valor.where(perda != 0, 100.0)
    return valor.where(ganho.notna())


def macd(
    fechamento: pd.Series, rapida: int = 12, lenta: int = 26, sinal: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    linha = mme(fechamento, rapida) - mme(fechamento, lenta)
    linha_sinal = mme(linha, sinal)
    return linha, linha_sinal, linha - linha_sinal


def bollinger(fechamento: pd.Series, n: int = 20, k: float = 2.0) -> tuple[pd.Series, pd.Series]:
    media = mm(fechamento, n)
    desvio = fechamento.rolling(n, min_periods=n).std(ddof=0)
    return media + k * desvio, media - k * desvio


def atr(maxima: pd.Series, minima: pd.Series, fechamento: pd.Series, n: int = 14) -> pd.Series:
    anterior = fechamento.shift(1)
    tr = pd.concat(
        [maxima - minima, (maxima - anterior).abs(), (minima - anterior).abs()], axis=1
    ).max(axis=1)
    return wilder(tr, n)


def calcular_indicadores(df: pd.DataFrame) -> pd.DataFrame:
    """Recebe colunas `maxima`, `minima`, `fechamento` e `volume`, indexadas
    por data em ordem crescente, e devolve as colunas de `indicadores_diarios`."""
    f = df["fechamento"].astype(float)
    hi = df["maxima"].astype(float)
    lo = df["minima"].astype(float)
    vol = df["volume"].astype(float)
    linha, linha_sinal, hist = macd(f)
    bb_sup, bb_inf = bollinger(f)
    saida = pd.DataFrame(
        {
            "mm20": mm(f, 20),
            "mm50": mm(f, 50),
            "mm200": mm(f, 200),
            "mme9": mme(f, 9),
            "rsi14": rsi(f, 14),
            "macd": linha,
            "macd_sinal": linha_sinal,
            "macd_hist": hist,
            "bb_superior": bb_sup,
            "bb_inferior": bb_inf,
            "atr14": atr(hi, lo, f, 14),
            "vol_media20": mm(vol, 20),
        },
        index=df.index,
    )
    return saida[COLUNAS]

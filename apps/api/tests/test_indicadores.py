import math

import pandas as pd
import pytest

from dominio.indicadores import COLUNAS, atr, bollinger, calcular_indicadores, macd, mm, mme, rsi

# Exemplo clássico de RSI(14) de Wilder publicado pela StockCharts.
FECHAMENTOS_RSI = [
    44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08, 45.89, 46.03,
    45.61, 46.28, 46.28, 46.00, 46.03, 46.41, 46.22, 45.64, 46.21, 46.25, 45.71, 46.45,
    45.78, 45.35, 44.03, 44.18, 44.22, 44.57, 43.42, 42.66, 43.13,
]  # fmt: skip
RSI_ESPERADO = [
    70.53, 66.32, 66.55, 69.41, 66.36, 57.97, 62.93, 63.26, 56.06, 62.38, 54.71, 50.42,
    39.99, 41.46, 41.87, 45.46, 37.30, 33.08, 37.77,
]  # fmt: skip


def test_rsi_bate_com_referencia_stockcharts():
    valores = rsi(pd.Series(FECHAMENTOS_RSI), 14)
    assert valores.iloc[:14].isna().all()
    # A tabela da StockCharts arredonda as médias intermediárias para 2 casas,
    # o que gera diferenças de até ~0,07 ponto nos primeiros valores.
    assert valores.iloc[14:].tolist() == pytest.approx(RSI_ESPERADO, abs=0.1)


def test_rsi_so_altas_vale_100():
    assert rsi(pd.Series(range(1, 20), dtype=float), 14).iloc[-1] == 100


def test_media_movel_simples():
    s = pd.Series([1.0, 2, 3, 4, 5])
    assert mm(s, 3).tolist()[2:] == [2, 3, 4]
    assert math.isnan(mm(s, 3).iloc[1])


def test_mme_semeada_pela_media_simples():
    # n=3 -> alpha 0.5; semente = média(1,2,3) = 2
    assert mme(pd.Series([1.0, 2, 3, 4, 5]), 3).tolist()[2:] == [2, 3, 4]


def test_bollinger_usa_desvio_populacional():
    sup, inf = bollinger(pd.Series([1.0, 2, 3]), 3, 2)
    desvio = math.sqrt(2 / 3)
    assert sup.iloc[2] == pytest.approx(2 + 2 * desvio)
    assert inf.iloc[2] == pytest.approx(2 - 2 * desvio)


def test_atr_wilder():
    hi = pd.Series([10.0, 11, 12, 11])
    lo = pd.Series([9.0, 9, 10, 10])
    fe = pd.Series([9.5, 10.5, 11.5, 10.5])
    # TR = [1, 2, 2, 1.5]; ATR3 = 5/3 e depois 5/3 + (1.5 - 5/3)/3
    v = atr(hi, lo, fe, 3)
    assert v.iloc[2] == pytest.approx(5 / 3)
    assert v.iloc[3] == pytest.approx(5 / 3 + (1.5 - 5 / 3) / 3)


def test_macd_e_zero_em_serie_constante():
    linha, sinal, hist = macd(pd.Series([10.0] * 60))
    assert linha.iloc[25] == pytest.approx(0)
    assert linha.iloc[24] != linha.iloc[24]  # NaN antes da MME26
    assert sinal.iloc[33] == pytest.approx(0)
    assert math.isnan(sinal.iloc[32])
    assert hist.iloc[-1] == pytest.approx(0)


def test_calcular_indicadores_aquecimento():
    n = 250
    df = pd.DataFrame(
        {
            "maxima": [10.0 + i * 0.1 + 0.5 for i in range(n)],
            "minima": [10.0 + i * 0.1 - 0.5 for i in range(n)],
            "fechamento": [10.0 + i * 0.1 for i in range(n)],
            "volume": [1000] * n,
        },
        index=pd.date_range("2024-01-01", periods=n).date,
    )
    ind = calcular_indicadores(df)
    assert list(ind.columns) == COLUNAS
    assert ind["mm200"].first_valid_index() == df.index[199]
    assert ind["mm20"].iloc[-1] == pytest.approx(df["fechamento"].iloc[-20:].mean())
    assert ind["vol_media20"].iloc[-1] == 1000
    assert ind["rsi14"].iloc[-1] == 100

import math
from datetime import date, timedelta
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from dominio.indicadores import calcular_indicadores
from dominio.metricas import calcular_metricas, classificar_tendencia


def serie(precos, inicio=date(2024, 1, 1), volume=1000):
    """Pregões em dias úteis consecutivos; máxima/mínima a ±1% do fechamento."""
    datas = pd.bdate_range(inicio, periods=len(precos)).date
    f = np.asarray(precos, dtype=float)
    return pd.DataFrame(
        {
            "maxima": f * 1.01,
            "minima": f * 0.99,
            "fechamento": f,
            "fechamento_ajustado": f,
            "volume": volume,
        },
        index=pd.Index(datas, name="data"),
    )


def metricas_de(df, fundamentos=None):
    return calcular_metricas(df, calcular_indicadores(df), fundamentos)


def test_vazio():
    assert calcular_metricas(serie([]), pd.DataFrame(), None) is None


def test_variacoes_em_serie_linear():
    # sobe 0,1% por pregão: 300 pregões cobrem mais de 12 meses
    precos = [100 * 1.001**i for i in range(300)]
    m = metricas_de(serie(precos))
    assert m.var_1d == pytest.approx(0.1, abs=0.01)
    assert m.preco == Decimal(str(precos[-1]))
    assert m.pregoes == 300
    # 30 dias corridos ~ 21 ou 22 pregões
    assert 2.0 < m.var_1m < 2.4
    assert m.var_12m is not None and 25 < m.var_12m < 30
    assert m.drawdown_12m == 0
    assert m.pos_52s > 95
    assert m.tendencia == "alta"


def test_janela_maior_que_o_historico_fica_nula():
    m = metricas_de(serie([10 + i * 0.01 for i in range(40)]))
    assert m.var_1m is not None
    assert m.var_3m is None and m.var_12m is None
    assert m.volatilidade_12m is None  # menos de 60 retornos
    assert m.tendencia is None  # sem MM200


def test_var_ano_usa_ultimo_pregao_do_ano_anterior():
    # 24/12 a 31/12/2024: 6 dias úteis a 10; depois 12 em 2025
    df = serie([10.0] * 6 + [12.0] * 5, inicio=date(2024, 12, 24))
    m = metricas_de(df)
    assert m.data.year == 2025
    assert m.var_ano == pytest.approx(20.0)


def test_volatilidade_e_drawdown():
    rng = np.random.default_rng(42)
    retornos = rng.normal(0, 0.02, 299)
    precos = 50 * np.exp(np.concatenate([[0], np.cumsum(retornos)]))
    m = metricas_de(serie(precos))
    assert m.volatilidade_12m == pytest.approx(2.0 * math.sqrt(252), rel=0.15)
    assert m.drawdown_12m < 0
    assert m.drawdown_12m >= -100


def test_posicao_52s_e_volume_financeiro():
    precos = [10.0] * 100 + [20.0] * 100 + [15.0] * 50
    m = metricas_de(serie(precos, volume=2000))
    assert m.max_52s == Decimal(str(20.0 * 1.01))
    assert m.min_52s == Decimal(str(10.0 * 0.99))
    esperado = (15 - 9.9) / (20.2 - 9.9) * 100
    assert m.pos_52s == pytest.approx(esperado, abs=0.01)
    assert m.volume_financeiro_20d == Decimal("30000.00")


def test_fundamentos_sao_copiados():
    m = metricas_de(serie([10.0] * 30), {"pl": 5.5, "dy_12m": 8.1, "valor_mercado": Decimal("1e9")})
    assert (m.pl, m.dy_12m, m.pvp) == (5.5, 8.1, None)
    assert m.valor_mercado == Decimal("1e9")


@pytest.mark.parametrize(
    ("preco", "mm50", "inclinacao", "esperado"),
    [
        (12, 11, 0.01, "alta"),
        (8, 9, -0.01, "baixa"),
        (12, 11, -0.01, "lateral"),  # alinhado, mas MM200 caindo
        (10.5, 11, 0.01, "lateral"),  # preço abaixo da MM50
    ],
)
def test_classificar_tendencia(preco, mm50, inclinacao, esperado):
    mm200 = pd.Series([10 + inclinacao * i for i in range(30)])
    assert classificar_tendencia(preco, mm50, mm200) == esperado


def test_tendencia_sem_historico_suficiente():
    assert classificar_tendencia(10, 9, pd.Series([8.0] * 10)) is None


def test_datas_sao_do_indice():
    df = serie([10.0] * 30, inicio=date(2025, 3, 3))
    assert metricas_de(df).data == df.index[-1]
    assert metricas_de(df).data - df.index[0] > timedelta(days=30)

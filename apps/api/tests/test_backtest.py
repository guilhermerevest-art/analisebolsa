from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from dominio import backtest as bt


def serie(fechamentos, aberturas=None, inicio=date(2020, 1, 1)) -> pd.DataFrame:
    """Pregões em dias corridos consecutivos; máxima e mínima a 1% do maior/menor preço."""
    fech = np.asarray(fechamentos, float)
    ab = np.asarray(aberturas if aberturas is not None else fechamentos, float)
    datas = [inicio + timedelta(days=i) for i in range(len(fech))]
    return pd.DataFrame(
        {
            "abertura": ab,
            "maxima": np.maximum(ab, fech) * 1.01,
            "minima": np.minimum(ab, fech) * 0.99,
            "fechamento": fech,
        },
        index=datas,
    )


SEM_CUSTO = bt.Custos(0.0, 0.0, 0.0)


def test_buy_and_hold_com_custos_calculados_a_mao():
    df = serie([10.0] * 299 + [11.0])
    custos = bt.Custos(corretagem=5.0, taxas=0.0003, deslizamento=0.0005)
    cfg = bt.Config("buy_and_hold", custos=custos, capital=10_000, cdi_no_caixa=False)
    r = bt.rodar(df, df.index[0], df.index[-1], {}, cfg)
    assert r is not None
    preco = 10 * 1.0005
    qtd = (10_000 - 5) / (preco * 1.0003)
    assert r.total.estrategia.retorno_total == pytest.approx(qtd * 11 / 10_000 - 1)
    (op,) = r.operacoes
    assert op.entrada == df.index[0] and op.motivo == "aberta" and op.saida is None
    assert op.preco_entrada == pytest.approx(preco)
    assert r.custos == pytest.approx(qtd * preco * 0.0003 + 5 + qtd * 10 * 0.0005, abs=0.01)
    # O buy and hold de referência usa os mesmos custos.
    assert r.total.buy_and_hold.retorno_total == pytest.approx(r.total.estrategia.retorno_total)


def test_sinal_no_fechamento_executa_na_abertura_seguinte():
    fech = [10.0] * 300
    fech[280:] = [12.0] * 20  # rompe a máxima dos 10 anteriores no pregão 280
    ab = list(fech)
    ab[281] = 12.5
    df = serie(fech, ab)
    cfg = bt.Config("rompimento", {"n_entrada": 10, "n_saida": 5}, custos=SEM_CUSTO)
    r = bt.rodar(df, df.index[0], df.index[-1], {}, cfg)
    (op,) = r.operacoes
    assert op.entrada == df.index[281]
    assert op.preco_entrada == pytest.approx(12.5)
    assert r.total.estrategia.operacoes == 1


def test_saida_por_sinal_e_resultado_liquido():
    fech = [10.0] * 300
    fech[200:230] = [12.0] * 30
    fech[230:] = [9.0] * 70  # fica abaixo da mínima dos 5 anteriores no pregão 230
    df = serie(fech)
    custos = bt.Custos(0.0, 0.001, 0.0)
    cfg = bt.Config("rompimento", {"n_entrada": 10, "n_saida": 5}, custos=custos)
    r = bt.rodar(df, df.index[0], df.index[-1], {}, cfg)
    (op,) = r.operacoes
    assert (op.entrada, op.saida, op.motivo) == (df.index[201], df.index[231], "sinal")
    assert op.resultado == pytest.approx(9 * (1 - 0.001) / (12 * 1.001) - 1)
    assert op.pregoes == 30
    assert r.total.estrategia.acertos == 0


def test_nenhuma_decisao_usa_dado_do_futuro():
    rng = np.random.default_rng(1)
    fech = 20 * np.exp(np.cumsum(rng.normal(0, 0.02, 600)))
    df = serie(fech, fech * (1 + rng.normal(0, 0.005, 600)))
    t = 400
    alterado = df.copy()
    alterado.iloc[t + 1 :] *= rng.uniform(0.5, 1.5, (600 - t - 1, 1))
    for codigo, params in [
        ("cruzamento_mm", {"curta": 10, "longa": 40}),
        ("rsi", {"rsi_entrada": 40, "rsi_saida": 60}),
        ("rompimento", {"n_entrada": 20, "n_saida": 10}),
        ("macd", {}),
        ("bollinger", {}),
        ("setup_91", {}),
        ("rsi", {"rsi_periodo": 2, "rsi_entrada": 10}),
    ]:
        params = bt.validar(codigo, params)
        a, b = bt.sinais(codigo, params, df), bt.sinais(codigo, params, alterado)
        assert (a[0][: t + 1] == b[0][: t + 1]).all() and (a[1][: t + 1] == b[1][: t + 1]).all()
        cfg = bt.Config(codigo, params, stop_atr=2)
        ra = bt.rodar(df, df.index[0], df.index[-1], {}, cfg)
        rb = bt.rodar(alterado, df.index[0], df.index[-1], {}, cfg)
        # Tudo o que foi decidido até o fechamento de t (executado até t+1) é igual.
        ate = df.index[t + 1]
        ops_a = [(o.entrada, o.saida) for o in ra.operacoes if o.entrada <= ate]
        ops_b = [(o.entrada, o.saida) for o in rb.operacoes if o.entrada <= ate]
        assert [(e, s if s and s <= ate else None) for e, s in ops_a] == [
            (e, s if s and s <= ate else None) for e, s in ops_b
        ]
        k = list(df.index).index(ate)
        pa = [p for p in ra.pontos if p.data < ate]
        pb = [p for p in rb.pontos if p.data < ate]
        assert pa == pb and k > 0


def test_stop_por_atr():
    fech = [10.0] * 450
    fech[200:210] = [12.0] * 10
    fech[210:] = [11.0] * 240  # queda maior que 1 ATR, sem sinal de saída (mínima de 100)
    df = serie(fech)
    cfg = bt.Config("rompimento", {"n_entrada": 10, "n_saida": 100}, stop_atr=1, custos=SEM_CUSTO)
    r = bt.rodar(df, df.index[0], df.index[-1], {}, cfg)
    (op,) = r.operacoes
    assert op.motivo == "stop" and op.saida == df.index[211]


def test_caixa_rende_cdi_fora_da_posicao():
    df = serie([10.0] * 400)  # IFR fica em 100: nunca entra
    cdi = {d: 0.04 for d in df.index}
    cfg = bt.Config("rsi", {"rsi_entrada": 30, "rsi_saida": 70})
    r = bt.rodar(df, df.index[100], df.index[-1], cdi, cfg)
    dias = 300
    assert r.total.estrategia.retorno_total == pytest.approx(1.0004**dias - 1)
    assert r.total.cdi.retorno_total == pytest.approx(1.0004**dias - 1)
    assert r.total.estrategia.exposicao == 0 and r.operacoes == []
    sem = bt.rodar(df, df.index[100], df.index[-1], cdi, bt.Config("rsi", cdi_no_caixa=False))
    assert sem.total.estrategia.retorno_total == 0


def test_divisao_dentro_e_fora_da_amostra():
    fech = np.linspace(10, 20, 400)
    df = serie(fech)
    r = bt.rodar(df, df.index[0], df.index[-1], {}, bt.Config("buy_and_hold", custos=SEM_CUSTO))
    corte = int(400 * 0.7)
    assert r.divisao == df.index[corte]
    assert r.dentro.buy_and_hold.retorno_total == pytest.approx(fech[corte - 1] / 10 - 1)
    assert r.fora.buy_and_hold.retorno_total == pytest.approx(20 / fech[corte - 1] - 1)
    total = (1 + r.dentro.estrategia.retorno_total) * (1 + r.fora.estrategia.retorno_total) - 1
    assert total == pytest.approx(r.total.estrategia.retorno_total)


def test_aquecimento_usa_historico_anterior_e_exige_um_ano():
    df = serie(np.linspace(10, 20, 400))
    cfg = bt.Config("cruzamento_mm", {"curta": 10, "longa": 100})
    r = bt.rodar(df, df.index[120], df.index[-1], {}, cfg)
    assert r.inicio == df.index[120]
    assert bt.rodar(df, df.index[200], df.index[-1], {}, cfg) is None  # 200 pregões
    # Sem histórico anterior, o período começa depois do aquecimento.
    r2 = bt.rodar(df, df.index[0], df.index[-1], {}, cfg)
    assert r2.inicio == df.index[101]


def test_metricas_drawdown_e_volatilidade():
    valores = np.array([110.0, 99.0, 121.0])
    m = bt.metricas(valores, 100.0, np.zeros(3))
    assert m.retorno_total == pytest.approx(0.21)
    assert m.drawdown_maximo == pytest.approx(99 / 110 - 1)
    assert m.retorno_anual is None  # menos de meio ano
    assert m.volatilidade > 0 and m.sharpe is not None


def test_pontos_reduzidos_por_semana_em_series_longas():
    df = serie(np.linspace(10, 30, 3000))
    r = bt.rodar(df, df.index[0], df.index[-1], {}, bt.Config("buy_and_hold"))
    assert len(r.pontos) < 500 and r.pontos[-1].data == df.index[-1]
    assert r.pontos[0].estrategia < 101


@pytest.mark.parametrize(
    ("codigo", "params", "erro"),
    [
        ("xyz", {}, "desconhecida"),
        ("cruzamento_mm", {"curta": 50, "longa": 50}, "menor"),
        ("rsi", {"rsi_entrada": 60}, "rsi_entrada"),
        ("rompimento", {"n_saida": 1}, "n_saida"),
        ("macd", {"macd_rapida": 30, "macd_lenta": 20}, "rápida"),
        ("bollinger", {"bb_desvios": 4}, "bb_desvios"),
    ],
)
def test_validacao(codigo, params, erro):
    with pytest.raises(bt.ParametrosInvalidos, match=erro):
        bt.validar(codigo, params)


def test_padroes_e_descricao():
    p = bt.validar("cruzamento_mm", {"curta": None, "longa": None})
    assert p == {"curta": 20, "longa": 100}
    assert "20" in bt.descrever("cruzamento_mm", p)


def test_ajuste_por_proventos():
    df = pd.DataFrame(
        {
            "abertura": [10.0],
            "maxima": [11.0],
            "minima": [9.0],
            "fechamento": [10.0],
            "fechamento_ajustado": [9.0],
        },
        index=[date(2024, 1, 2)],
    )
    a = bt.ajustar(df)
    assert a.iloc[0].tolist() == pytest.approx([9.0, 9.9, 8.1, 9.0])


def test_textos_sem_linguagem_de_recomendacao():
    from tests.test_insights import PROIBIDAS

    textos = [bt.AVISO.replace("Não é recomendação de investimento.", "")]
    for e in bt.ESTRATEGIAS.values():
        textos += [e.nome, bt.descrever(e.codigo, bt.validar(e.codigo, {}))]
        textos += [p.rotulo for p in e.parametros]
    for t in textos:
        assert not PROIBIDAS.search(t), t


def test_setup_91_entra_na_virada_da_media():
    fech = np.concatenate([np.linspace(20, 10, 200), np.linspace(10, 20, 200)])
    df = serie(fech)
    p = bt.validar("setup_91", {})
    entrada, saida = bt.sinais("setup_91", p, df)
    (i,) = np.flatnonzero(entrada)
    assert 200 <= i <= 205 and not saida.any()


def test_bollinger_entra_abaixo_da_banda_e_sai_acima_da_media():
    fech = [10.0, 10.2] * 50 + [8.0] + [10.5] * 10
    df = serie(fech)
    entrada, saida = bt.sinais("bollinger", bt.validar("bollinger", {}), df)
    assert np.flatnonzero(entrada).tolist() == [100]
    assert saida[101]


def test_datas_das_operacoes_ficam_nos_pontos_reduzidos():
    rng = np.random.default_rng(3)
    fech = 20 * np.exp(np.cumsum(rng.normal(0, 0.02, 3000)))
    df = serie(fech)
    r = bt.rodar(df, df.index[0], df.index[-1], {}, bt.Config("rsi", {"rsi_periodo": 2}))
    datas = {p.data for p in r.pontos}
    assert len(r.operacoes) > 10 and len(datas) < 3000
    assert all(o.entrada in datas and (o.saida is None or o.saida in datas) for o in r.operacoes)
    ponto = next(p for p in r.pontos if p.data == r.operacoes[0].entrada)
    assert ponto.preco == pytest.approx(df.loc[ponto.data, "fechamento"], abs=1e-4)

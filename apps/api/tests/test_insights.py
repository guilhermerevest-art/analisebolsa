import re
from datetime import date
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from dominio import formato as f
from dominio import insights as ins
from dominio.insights import Contexto, elegibilidade, gerar_insights
from dominio.metricas import Metricas

N = 300  # pregões da janela


def contexto(fech=None, volume=None, metricas=None, setor="Bancos", dy_anos=(), pl_pares=(), **ind):
    """Contexto sintético: fechamento constante em 10 e indicadores neutros, exceto o que
    o teste passar."""
    fech = np.full(N, 10.0) if fech is None else np.asarray(fech, dtype=float)
    n = len(fech)
    datas = pd.Index(pd.bdate_range(date(2024, 1, 1), periods=n).date, name="data")
    vol = np.full(n, 1000.0) if volume is None else np.asarray(volume, dtype=float)
    cot = pd.DataFrame({"fechamento": fech, "volume": vol}, index=datas)
    base = {
        "mm50": np.full(n, 10.0), "mm200": np.full(n, 10.0), "rsi14": np.full(n, 50.0),
        "macd": np.zeros(n), "macd_sinal": np.zeros(n),
        "bb_superior": fech * 1.05, "bb_inferior": fech * 0.95,
    }  # fmt: skip
    base |= {k: np.asarray(v, dtype=float) for k, v in ind.items()}
    m = {"data": datas[-1], "preco": Decimal(str(fech[-1])), "pregoes": 1000,
         "volume_financeiro_20d": Decimal("1000000")} | (metricas or {})  # fmt: skip
    return Contexto(
        cot, pd.DataFrame(base, index=datas), Metricas(**m), setor, list(dy_anos), list(pl_pares)
    )


def degrau(antes, depois, atras):
    """Série que muda de `antes` para `depois` há `atras` pregões."""
    s = np.full(N, float(antes))
    s[N - 1 - atras :] = depois
    return s


def queda_vol_bandas():
    larg = np.linspace(2.0, 0.5, N)
    fech = np.full(N, 10.0)
    return {"bb_superior": fech + larg / 2, "bb_inferior": fech - larg / 2}


# (código esperado, contexto) — cada regra disparando em cada direção
CASOS = {
    "cruzamento_mm50_mm200_alta": lambda: contexto(mm50=degrau(9, 11, 2)),
    "cruzamento_mm50_mm200_baixa": lambda: contexto(mm50=degrau(11, 9, 0)),
    "preco_mm200_acima": lambda: contexto(fech=degrau(9, 11, 3)),
    "preco_mm200_abaixo": lambda: contexto(fech=degrau(11, 9, 4)),
    "distancia_mm200": lambda: contexto(metricas={"dist_mm200": -25.0}),
    "rsi_sobrecompra": lambda: contexto(rsi14=np.full(N, 76.4)),
    "rsi_sobrevenda": lambda: contexto(rsi14=np.full(N, 24.0)),
    "macd_cruzamento_alta": lambda: contexto(macd=degrau(-1, 1, 0)),
    "macd_cruzamento_baixa": lambda: contexto(macd=degrau(1, -1, 0)),
    "maxima_52s": lambda: contexto(fech=np.linspace(8, 12, N)),
    "minima_52s": lambda: contexto(fech=np.linspace(12, 8, N)),
    "bollinger_compressao": lambda: contexto(**queda_vol_bandas()),
    "bollinger_rompimento": lambda: contexto(bb_superior=np.full(N, 9.5)),
    "volume_anormal": lambda: contexto(
        volume=np.r_[np.full(N - 1, 1000.0), 3000.0], metricas={"var_1d": -2.5}
    ),
    "volatilidade_alta": lambda: contexto(
        fech=np.r_[np.full(N - 20, 10.0), 10 * np.cumprod(np.tile([1.05, 0.95], 10))],
        metricas={"volatilidade_12m": 20.0},
    ),
    "tendencia": lambda: contexto(metricas={"tendencia": "alta"}),
    "dy_historico": lambda: contexto(metricas={"dy_12m": 8.0}, dy_anos=[5, 6, 5.5]),
    "pl_setor": lambda: contexto(metricas={"pl": 3.0}, pl_pares=[5, 6, 7, 8, 9, 10]),
}


@pytest.mark.parametrize("codigo", CASOS)
def test_cada_regra_dispara(codigo):
    assert codigo in {i.codigo for i in gerar_insights(CASOS[codigo]())}


def test_contexto_neutro_nao_gera_insight():
    assert gerar_insights(contexto()) == []


def test_cruzamento_informa_ha_quantos_pregoes():
    i = ins.cruzamento_medias(contexto(mm50=degrau(9, 11, 2)))
    assert i.tom == "positivo" and "há 2 pregões" in i.texto and "golden cross" in i.texto
    assert ins.cruzamento_medias(contexto(mm50=degrau(9, 11, 0))).texto.count("no último pregão")


def test_cruzamento_antigo_nao_dispara():
    assert ins.cruzamento_medias(contexto(mm50=degrau(9, 11, 8))) is None
    assert ins.macd(contexto(macd=degrau(-1, 1, 1))) is None


def test_rsi_texto_com_valor_e_faixa():
    i = ins.rsi(contexto(rsi14=np.full(N, 76.4)))
    assert "76" in i.texto and "acima de 70" in i.texto
    assert ins.rsi(contexto(rsi14=np.full(N, 69.0))) is None


def test_distancia_mm200_limite():
    assert ins.distancia_mm200(contexto(metricas={"dist_mm200": 19.9})) is None
    assert "25,0% abaixo" in ins.distancia_mm200(contexto(metricas={"dist_mm200": -25.0})).texto


def test_extremos_52s_no_meio_nao_dispara():
    fech = np.r_[np.linspace(8, 12, N - 10), np.full(10, 10.0)]
    assert ins.extremos_52s(contexto(fech=fech)) is None


def test_bandas_largas_nao_comprimem():
    b = queda_vol_bandas()
    b["bb_superior"][-1] = 12.0
    assert ins.bollinger_compressao(contexto(**b)) is None


def test_volume_texto():
    i = ins.volume_anormal(CASOS["volume_anormal"]())
    assert "3,0 vezes" in i.texto and "queda de 2,50%" in i.texto
    assert ins.volume_anormal(contexto(volume=np.r_[np.full(N - 1, 1000.0), 2000.0])) is None


def test_tendencia_lateral_e_baixa():
    lateral = ins.tendencia(contexto(metricas={"tendencia": "lateral"}))
    assert lateral.tom == "neutro" and "não estão alinhados" in lateral.texto
    em_ordem = contexto(
        fech=np.full(N, 12.0), mm50=np.full(N, 11.0), metricas={"tendencia": "lateral"}
    )
    assert "mas a média de 200 não subiu" in ins.tendencia(em_ordem).texto
    assert ins.tendencia(contexto(metricas={"tendencia": "baixa"})).tom == "atencao"
    assert ins.tendencia(contexto()) is None


def test_dy_precisa_de_tres_anos_e_superar_a_media():
    assert ins.dy_historico(contexto(metricas={"dy_12m": 8.0}, dy_anos=[5, 6])) is None
    assert ins.dy_historico(contexto(metricas={"dy_12m": 4.0}, dy_anos=[5, 6, 5])) is None


def test_pl_setor():
    pares = [5, 6, 7, 8, 9, 10]
    alto = ins.pl_setor(contexto(metricas={"pl": 30.0}, pl_pares=pares))
    assert alto.titulo == "P/L alto em relação ao setor" and "setor Bancos" in alto.texto
    assert ins.pl_setor(contexto(metricas={"pl": 7.5}, pl_pares=pares)) is None
    assert ins.pl_setor(contexto(metricas={"pl": 3.0}, pl_pares=pares[:4])) is None
    assert ins.pl_setor(contexto(metricas={"pl": -3.0}, pl_pares=pares)) is None


def test_ativo_inelegivel_so_recebe_fundamentos():
    m = {"pregoes": 120, "rsi14": 80, "dy_12m": 8.0}
    c = contexto(metricas=m, rsi14=np.full(N, 80.0), dy_anos=[5, 6, 5])
    assert [i.codigo for i in gerar_insights(c)] == ["dy_historico"]
    assert elegibilidade(120, 1e6)[0] is False
    ok, motivo = elegibilidade(500, 50_000)
    assert not ok and "R$ 50.000,00" in motivo
    assert elegibilidade(500, 100_000) == (True, None)


def test_ordem_por_prioridade():
    c = contexto(metricas={"tendencia": "alta"}, rsi14=np.full(N, 80.0))
    assert [i.codigo for i in gerar_insights(c)] == ["tendencia", "rsi_sobrecompra"]


def test_formato_pt_br():
    assert f.brl(1234.5) == "R$ 1.234,50"
    assert f.pct(-3.456, 2) == "-3,46%"
    assert f.num(1_000_000, 0) == "1.000.000"
    assert f.quando(1) == "há 1 pregão"


PROIBIDAS = re.compile(
    r"\bcompr(e|ar|em)\b|\bvend(a|er|am)\b|recomend|oportunidade|garantid|lucro certo|"
    r"\bmelhor|\bbarat|chance|probabilidade|\bdeve\b",
    re.IGNORECASE,
)


def test_nenhum_texto_tem_linguagem_de_recomendacao():
    """Gera os textos de todas as regras, nas duas direções, e procura linguagem proibida."""
    extras = [contexto(metricas={"tendencia": t}) for t in ("alta", "baixa", "lateral")] + [
        contexto(metricas={"pl": 30.0}, pl_pares=[5, 6, 7, 8, 9, 10]),
        contexto(bb_inferior=np.full(N, 10.5)),
        contexto(metricas={"dist_mm200": 30.0}),
        contexto(metricas={"pregoes": 10}),
    ]
    textos = [
        t
        for c in [fn() for fn in CASOS.values()] + extras
        for i in gerar_insights(c)
        for t in (i.titulo, i.texto)
    ]
    textos += [elegibilidade(10, 1e6)[1], elegibilidade(500, 0)[1]]
    assert len(textos) > 40
    for t in textos:
        assert not PROIBIDAS.search(t), t
        assert "nan" not in t.lower().split() and "None" not in t, t

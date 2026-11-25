import re
from datetime import date

import numpy as np
import pandas as pd
import pytest

from dominio.cenarios import (
    Nivel,
    agrupar,
    calcular_cenarios,
    calcular_niveis,
    montar_cenarios,
    pivos,
)


def semanal(maximas, minimas=None, fechamentos=None):
    maximas = np.asarray(maximas, dtype=float)
    minimas = maximas - 1 if minimas is None else np.asarray(minimas, dtype=float)
    fech = (maximas + minimas) / 2 if fechamentos is None else np.asarray(fechamentos, float)
    datas = pd.date_range("2023-01-02", periods=len(maximas), freq="W-MON").date
    return pd.DataFrame({"maxima": maximas, "minima": minimas, "fechamento": fech}, index=datas)


def ondas():
    """Oscila entre ~10 e ~20 com topos em 20, 20.2 e 25 e fundos em 10, 10.1 e 5."""
    topos = {10: 20.0, 30: 20.2, 50: 25.0}
    fundos = {20: 10.0, 40: 10.1, 60: 5.0}
    alta = np.full(80, 15.0)
    baixa = np.full(80, 14.0)
    for i, v in topos.items():
        alta[i] = v
    for i, v in fundos.items():
        baixa[i] = v
    return semanal(alta, baixa)


def test_pivos_encontra_topos_e_fundos_plantados():
    assert sorted(pivos(ondas())) == [5.0, 10.0, 10.1, 20.0, 20.2, 25.0]


def test_pivo_precisa_ser_estrito_nas_duas_semanas():
    s = semanal([10, 11, 12, 12, 11, 10, 9])
    assert 12.0 not in pivos(s)  # duas semanas iguais no topo não formam pivô


def test_agrupa_pivos_proximos_pela_media():
    assert agrupar([10.0, 10.1, 20.0, 20.2, 25.0], distancia=1.0) == [
        (10.05, 2),
        (20.1, 2),
        (25.0, 1),
    ]


def test_niveis_separa_suportes_e_resistencias():
    niveis, atr = calcular_niveis(ondas(), preco=15.0, max_52s=26.0, min_52s=4.0)
    assert atr > 0
    sup = [n for n in niveis if n.tipo == "suporte"]
    res = [n for n in niveis if n.tipo == "resistencia"]
    assert sup[0].preco == pytest.approx(10.05) and sup[0].toques == 2
    assert res[0].preco == pytest.approx(20.1) and res[0].toques == 2
    assert {n.tipo for n in niveis} == {"suporte", "resistencia", "max_52s", "min_52s"}


def test_cenarios_com_dois_niveis_de_cada_lado():
    niveis = [Nivel(10, "suporte", 2), Nivel(8, "suporte", 1),
              Nivel(12, "resistencia", 2), Nivel(15, "resistencia", 1)]  # fmt: skip
    alta, lateral, baixa = montar_cenarios(niveis, preco=11.0, atr_diario=0.4)
    assert (alta.gatilho, alta.alvo) == (12, 15)
    assert alta.invalidacao == pytest.approx(12 - 0.6)
    assert alta.dist_gatilho == pytest.approx(9.09)
    assert alta.relacao == pytest.approx(3 / 0.6)
    assert (lateral.limite_inferior, lateral.limite_superior) == (10, 12)
    assert (baixa.gatilho, baixa.alvo) == (10, 8)
    assert baixa.invalidacao == pytest.approx(10.6)
    assert "Se o preço fechar acima de R$ 12,00 (+9,1%)" in alta.texto
    assert "abaixo de R$ 11,40" in alta.texto


def test_sem_segundo_nivel_o_alvo_usa_atr():
    alta, _, baixa = montar_cenarios(
        [Nivel(10, "suporte", 1), Nivel(12, "resistencia", 1)], preco=11.0, atr_diario=0.5
    )
    assert alta.alvo == pytest.approx(13.0)
    assert baixa.alvo == pytest.approx(9.0)


def test_na_maxima_historica_nao_ha_cenario_de_alta():
    cenarios = montar_cenarios([Nivel(10, "suporte", 1)], preco=11.0, atr_diario=0.5)
    assert [c.tipo for c in cenarios] == ["baixa"]


def test_calcular_cenarios_exige_atr_e_historico():
    s = ondas()
    assert calcular_cenarios(s, date(2024, 7, 1), 15.0, None, 25.0, 5.0) is None
    assert calcular_cenarios(s.tail(20), date(2024, 7, 1), 15.0, 0.5, 25.0, 5.0) is None
    analise = calcular_cenarios(s, date(2024, 7, 1), 15.0, 0.5, 25.0, 5.0)
    assert [c.tipo for c in analise.cenarios] == ["alta", "lateral", "baixa"]
    assert analise.niveis_json()[0]["tipo"] == "suporte"


PROIBIDAS = re.compile(
    r"\bcompr(e|ar|em)\b|\bvend(a|er|am)\b|recomend|oportunidade|garantid|lucro certo|"
    r"\bmelhor|\bbarat|chance|probabilidade|stop|\bentrar\b|\bsair\b",
    re.IGNORECASE,
)


def test_textos_dos_cenarios_sao_condicionais_e_sem_recomendacao():
    analise = calcular_cenarios(ondas(), date(2024, 7, 1), 15.0, 0.5, 25.0, 5.0)
    for c in analise.cenarios:
        assert not PROIBIDAS.search(c.titulo + c.texto), c.texto
        if c.tipo != "lateral":
            assert c.texto.startswith("Se o preço fechar") and "perde validade" in c.texto


def test_extremo_de_52_semanas_igual_a_um_nivel_nao_duplica():
    niveis, _ = calcular_niveis(ondas(), preco=15.0, max_52s=25.0, min_52s=4.0)
    assert "max_52s" not in {n.tipo for n in niveis}
    assert "min_52s" in {n.tipo for n in niveis}

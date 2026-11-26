from datetime import date, timedelta
from decimal import Decimal

import pytest

from dominio.modelos import Provento
from dominio.simulador import (
    AVISO,
    EXPLICACAO_FAIXA,
    MESES_MINIMOS,
    faixa_simulada,
    retornos_mensais,
    semente,
    simular,
)
from tests.test_insights import PROIBIDAS


def dias_uteis(inicio: date, fim: date) -> list[date]:
    d, saida = inicio, []
    while d <= fim:
        if d.weekday() < 5:
            saida.append(d)
        d += timedelta(days=1)
    return saida


def constante(dias, preco="10"):
    return {d: Decimal(preco) for d in dias}


def test_aportes_mensais_em_ativo_constante_sem_proventos():
    dias = dias_uteis(date(2024, 1, 2), date(2024, 3, 29))
    pontos = simular(date(2024, 1, 1), 1000, 100, precos=constante(dias))
    assert [p.data for p in pontos] == [date(2024, 1, 31), date(2024, 2, 29), date(2024, 3, 29)]
    assert [p.aportado for p in pontos] == [1100, 1200, 1300]
    assert [p.patrimonio for p in pontos] == [1100, 1200, 1300]
    assert pontos[-1].proventos == 0
    assert pontos[-1].cdi is None and pontos[-1].ipca is None


def test_dividendo_conhecido_reinvestido_no_pagamento():
    dias = dias_uteis(date(2024, 1, 2), date(2024, 2, 29))
    # R$ 1 por ação com data-com 10/01 e pagamento 15/02; o preço fica em 10 (sem queda, para
    # isolar a conta): 100 ações recebem R$ 100, que compram mais 10 ações.
    prov = [Provento("dividendo", date(2024, 1, 10), Decimal("1"), date(2024, 2, 15))]
    jan, fev = simular(date(2024, 1, 1), 1000, 0, precos=constante(dias), proventos=prov)
    assert jan.proventos == 100
    assert jan.patrimonio == 1100  # 1.000 em ações mais 100 a receber
    assert fev.patrimonio == 1100  # 110 ações
    sem = simular(
        date(2024, 1, 1), 1000, 0, precos=constante(dias), proventos=prov, reinvestir=False
    )
    assert sem[-1].patrimonio == 1100 and sem[-1].proventos == 100


def test_provento_apos_desdobramento_conta_unidades_ajustadas():
    dias = dias_uteis(date(2024, 1, 2), date(2024, 1, 31))
    # Desdobramento 1:2 com data-com 15/01: o banco tem preço ajustado 10 em todo o mês
    # (20 antes do evento na época). Um provento de R$ 2 por ação na data-com 05/01 equivale
    # a R$ 1 por unidade ajustada. Aporte de 1.000 = 100 unidades ajustadas = 50 ações da época.
    prov = [
        Provento("dividendo", date(2024, 1, 5), Decimal("2"), date(2024, 1, 20)),
        Provento("desdobramento", date(2024, 1, 15), Decimal("2")),
    ]
    (jan,) = simular(date(2024, 1, 1), 1000, 0, precos=constante(dias), proventos=prov)
    assert jan.proventos == 100


def test_cdi_com_taxa_fixa_bate_com_a_formula_fechada():
    dias = dias_uteis(date(2024, 1, 2), date(2024, 12, 31))
    taxa = 0.04
    cdi = {d: taxa for d in dias}
    pontos = simular(date(2024, 1, 1), 1000, 0, cdi=cdi)
    esperado = 1000 * (1 + taxa / 100) ** (len(dias) - 1)
    assert pontos[-1].cdi == pytest.approx(esperado, abs=0.01)
    assert pontos[-1].patrimonio is None and pontos[-1].proventos is None

    # Com aporte mensal: cada aporte rende desde o seu dia.
    pontos = simular(date(2024, 1, 1), 0, 100, cdi=cdi)
    primeiros = [d for i, d in enumerate(dias) if i == 0 or d.month != dias[i - 1].month]
    esperado = sum(100 * (1 + taxa / 100) ** (len(dias) - 1 - dias.index(d)) for d in primeiros)
    assert pontos[-1].cdi == pytest.approx(esperado, abs=0.01)


def test_ipca_corrige_na_virada_do_mes():
    dias = dias_uteis(date(2024, 1, 2), date(2024, 3, 29))
    ipca = {date(2024, 1, 1): 1.0, date(2024, 2, 1): 0.5}
    pontos = simular(date(2024, 1, 1), 1000, 0, precos=constante(dias), ipca=ipca)
    assert [p.ipca for p in pontos] == [1000, 1010, pytest.approx(1015.05)]


def test_sem_dados_no_periodo():
    assert simular(date(2030, 1, 1), 1000, 0, cdi={date(2024, 1, 2): 0.04}) == []


def test_retornos_mensais_totais_com_provento_na_data_ex():
    dias = dias_uteis(date(2024, 1, 2), date(2024, 3, 29))
    precos = constante(dias)
    # Preço sobe para 11 em fevereiro; provento de R$ 0,50 com data-com 14/03.
    for d in dias:
        if d.month >= 2:
            precos[d] = Decimal("11")
    prov = [Provento("jcp", date(2024, 3, 14), Decimal("0.5"))]
    fev, mar = retornos_mensais(precos, prov)
    assert fev == pytest.approx(0.1)
    assert mar == pytest.approx(0.5 / 11)


def test_faixa_reprodutivel_com_a_mesma_semente():
    retornos = [0.01 * ((i % 7) - 3) for i in range(MESES_MINIMOS)]
    datas = [date(2020 + m // 12, m % 12 + 1, 28) for m in range(36)]
    a = faixa_simulada(retornos, datas, 1000, 100, semente("X", 1))
    b = faixa_simulada(retornos, datas, 1000, 100, semente("X", 1))
    c = faixa_simulada(retornos, datas, 1000, 100, semente("X", 2))
    assert a == b and a != c
    assert len(a.pontos) == 36 and a.meses_historico == MESES_MINIMOS
    assert all(p.p10 <= p.p50 <= p.p90 for p in a.pontos)


def test_faixa_com_retorno_constante_e_deterministica():
    datas = [date(2020, m + 1, 28) for m in range(3)]
    faixa = faixa_simulada([0.01] * MESES_MINIMOS, datas, 1000, 100, 7)
    esperado = ((1000 + 100) * 1.01 + 100) * 1.01
    assert faixa.pontos[1].p10 == faixa.pontos[1].p90 == pytest.approx(esperado, abs=0.01)


def test_faixa_exige_historico_minimo():
    datas = [date(2020, 1, 28), date(2020, 2, 28)]
    assert faixa_simulada([0.01] * (MESES_MINIMOS - 1), datas, 1000, 0, 1) is None


def test_textos_sem_linguagem_de_recomendacao():
    for t in (AVISO, EXPLICACAO_FAIXA):
        assert not PROIBIDAS.search(t), t


def test_aportes_no_dolar_pela_ptax_de_cada_dia():
    from dominio.simulador import simular as sim

    cdi = {date(2024, 1, 2): 0.0, date(2024, 2, 1): 0.0, date(2024, 2, 29): 0.0}
    dolar = {date(2023, 12, 29): 5.0, date(2024, 2, 1): 4.0, date(2024, 2, 29): 6.0}
    pontos = sim(date(2024, 1, 1), 1000, 1000, cdi=cdi, dolar=dolar)
    jan, fev = pontos
    # Janeiro: 2.000 (inicial + mensal) a 5,00 = 400 dólares, valendo 2.000.
    assert jan.dolar == 2000.0
    # Fevereiro: +1.000 a 4,00 = 250 dólares; 650 a 6,00 = 3.900.
    assert fev.dolar == 3900.0 and fev.aportado == 3000.0
    assert sim(date(2024, 1, 1), 1000, 0, cdi=cdi)[0].dolar is None

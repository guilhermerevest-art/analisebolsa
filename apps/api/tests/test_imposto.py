from datetime import date
from decimal import Decimal as D

import pytest

from dominio.carteira import Operacao, VendaRealizada, consolidar
from dominio.imposto import apurar, dia_util_bancario, pascoa, ultimo_dia_util_do_mes_seguinte
from tests.test_api import cliente, token  # noqa: F401 (fixture)
from tests.test_api_carteira import api, auth, lancar, nova_carteira  # noqa: F401

TIPOS = {"PETR4": "acao", "VALE3": "acao", "HGLG11": "fii", "BOVA11": "etf", "AAPL34": "bdr"}


def venda(ticker, dia, valor, resultado):
    valor, resultado = D(str(valor)), D(str(resultado))
    return VendaRealizada(ticker, dia, D(1), valor, D(0), valor - resultado, resultado)


def test_acoes_isentas_ate_20_mil_de_vendas():
    m = apurar([venda("PETR4", date(2026, 3, 10), 15000, 3000)], TIPOS).meses[0]
    assert m.isento_acoes and m.ganho_isento == 3000
    assert m.base_comum == 0 and m.darf == 0 and m.vencimento is None
    # Exatamente R$ 20.000,00 ainda é isento.
    assert apurar([venda("PETR4", date(2026, 3, 10), 20000, 100)], TIPOS).meses[0].isento_acoes


def test_acoes_tributadas_acima_de_20_mil_com_irrf():
    m = apurar([venda("PETR4", date(2026, 3, 10), 30000, 5000)], TIPOS).meses[0]
    assert not m.isento_acoes
    assert m.imposto_comum == D("750.00")
    assert m.irrf == D("1.50")  # 0,005% de 30.000
    assert m.darf == D("748.50") and m.vencimento == date(2026, 4, 30)


def test_prejuizo_compensa_nos_meses_seguintes_inclusive_de_mes_isento():
    ap = apurar(
        [
            venda("PETR4", date(2026, 1, 5), 10000, -1000),  # mês isento, mas prejuízo conta
            venda("VALE3", date(2026, 2, 5), 25000, -2000),
            venda("PETR4", date(2026, 3, 5), 30000, 5000),
        ],
        TIPOS,
    )
    jan, fev, mar = ap.meses
    assert jan.prejuizo_comum == 1000 and fev.prejuizo_comum == 3000
    assert mar.compensado_comum == 3000 and mar.base_comum == 2000
    # IRRF de fevereiro (1,25, sem imposto naquele mês) fica de saldo e abate em março.
    assert mar.imposto_comum == D("300.00") and mar.darf == D("297.25")
    assert ap.prejuizo_comum == 0


def test_ganho_isento_nao_consome_prejuizo_e_etf_nao_tem_isencao():
    ap = apurar(
        [
            venda("VALE3", date(2026, 1, 5), 25000, -500),
            venda("PETR4", date(2026, 2, 5), 10000, 800),  # isento: prejuízo fica
            venda("BOVA11", date(2026, 2, 6), 5000, 1000),  # ETF: tributa, compensa
        ],
        TIPOS,
    )
    fev = ap.meses[1]
    assert fev.ganho_isento == 800 and fev.compensado_comum == 500
    assert fev.base_comum == 500 and fev.imposto_comum == D("75.00")
    # IRRF de fevereiro (0,75) é dispensado; o de janeiro (1,25) abate agora.
    assert fev.irrf == 0 and fev.darf == D("73.75")


def test_fii_a_20_por_cento_e_prejuizo_separado():
    ap = apurar(
        [
            venda("VALE3", date(2026, 1, 5), 25000, -4000),
            venda("HGLG11", date(2026, 2, 5), 8000, 1000),
            venda("HGLG11", date(2026, 3, 5), 8000, -300),
            venda("HGLG11", date(2026, 4, 5), 8000, 500),
        ],
        TIPOS,
    )
    _, fev, mar, abr = ap.meses
    assert fev.imposto_fii == D("200.00") and fev.compensado_comum == 0
    assert fev.prejuizo_comum == 4000  # prejuízo de ações não abate FII
    assert mar.prejuizo_fii == 300
    assert abr.base_fii == 200 and abr.imposto_fii == D("40.00")


def test_darf_abaixo_de_10_reais_passa_para_o_mes_seguinte():
    ap = apurar(
        [
            venda("BOVA11", date(2026, 1, 5), 5000, 50),  # 7,50
            venda("AAPL34", date(2026, 2, 5), 5000, 30),  # 4,50 + 7,50
        ],
        TIPOS,
    )
    jan, fev = ap.meses
    assert jan.darf == 0 and jan.fica_para_depois == D("7.50")
    assert fev.acumulado_anterior == D("7.50") and fev.darf == D("12.00")
    assert ap.pendente == 0


def test_irrf_maior_que_o_imposto_fica_para_depois():
    ap = apurar(
        [
            venda("PETR4", date(2026, 1, 5), 100000, 0),  # IRRF 5,00, imposto 0
            venda("PETR4", date(2026, 2, 5), 30000, 100),  # 15,00 − (5,00 + 1,50)
        ],
        TIPOS,
    )
    jan, fev = ap.meses
    assert jan.irrf == D("5.00") and jan.saldo_irrf == D("5.00")
    assert fev.irrf_usado == D("6.50") and fev.darf == D("0") and fev.fica_para_depois == D("8.50")


def dt(ticker, dia, valor, resultado):
    valor, resultado = D(str(valor)), D(str(resultado))
    return VendaRealizada(ticker, dia, D(1), valor, D(0), valor - resultado, resultado, True)


def test_day_trade_20_por_cento_sem_isencao_e_irrf_de_1_por_cento():
    ap = apurar(
        [
            dt("PETR4", date(2026, 5, 4), 10000, 500),
            dt("VALE3", date(2026, 5, 4), 8000, -100),  # mesmo dia: IRRF sobre 400
            venda("PETR4", date(2026, 5, 20), 15000, 1000),  # comum, isenta
            venda("XYZW3", date(2026, 5, 21), 1, 0),
        ],
        TIPOS,
    )
    (m,) = ap.meses
    # As vendas de day trade não contam para os R$ 20 mil: as ações seguem isentas.
    # (o ativo sem tipo cadastrado conta como ação: 15.001)
    assert m.vendas_acoes == 15001 and m.isento_acoes and m.ganho_isento == 1000
    assert m.resultado_day_trade == 400 and m.imposto_day_trade == D("80.00")
    assert m.irrf == D("4.00")  # 1% de 400; o 0,005% de 15.000 (0,75) é dispensado
    assert m.darf == D("76.00")
    assert ap.day_trade == [("PETR4", date(2026, 5, 4)), ("VALE3", date(2026, 5, 4))]
    assert ap.sem_tipo == ["XYZW3"]


def test_prejuizo_de_day_trade_so_compensa_day_trade():
    ap = apurar(
        [
            dt("PETR4", date(2026, 5, 4), 10000, -300),
            venda("PETR4", date(2026, 6, 4), 30000, 1000),
            dt("VALE3", date(2026, 7, 4), 10000, 500),
        ],
        TIPOS,
    )
    mai, jun, jul = ap.meses
    assert mai.prejuizo_day_trade == 300 and jun.compensado_day_trade == 0
    assert jun.base_comum == 1000
    assert jul.compensado_day_trade == 300 and jul.base_day_trade == 200
    assert jul.imposto_day_trade == D("40.00")


def test_day_trade_na_consolidacao():
    c = consolidar(
        [
            Operacao(1, "PETR4", "compra", date(2026, 1, 2), D(100), D(30), D(0)),
            # Dia com compra de 300 e venda de 200: 200 casadas são day trade.
            Operacao(2, "PETR4", "compra", date(2026, 2, 2), D(300), D(40), D(6)),
            Operacao(3, "PETR4", "venda", date(2026, 2, 2), D(200), D(41), D(4)),
            # Dia com venda maior que a compra: 50 casadas e 50 da posição.
            Operacao(4, "PETR4", "compra", date(2026, 3, 2), D(50), D(42), D(0)),
            Operacao(5, "PETR4", "venda", date(2026, 3, 2), D(100), D(43), D(0)),
        ]
    )
    dt_fev, dt_mar, comum_mar = c.vendas
    # Fevereiro: custo unitário do dia (12.006 / 300) = 40,02; venda 8.200 − 4 − 8.004.
    assert dt_fev.day_trade and dt_fev.quantidade == 200 and dt_fev.resultado == D("192")
    # A sobra de 100 entra na posição pelo custo do dia: (3.000 + 4.002) / 200 = 35,01.
    assert dt_mar.day_trade and dt_mar.resultado == D("50")  # (43 − 42) × 50
    assert not comum_mar.day_trade and comum_mar.quantidade == 50
    assert comum_mar.custo_medio == D("1750.50") and comum_mar.resultado == D("399.50")
    pos = c.posicoes["PETR4"]
    assert pos.quantidade == 150 and pos.preco_medio == D("35.01")


def test_vendas_vem_da_consolidacao_com_custos():
    c = consolidar(
        [
            Operacao(1, "PETR4", "compra", date(2026, 1, 2), D(100), D(30), D("5")),
            Operacao(2, "PETR4", "compra", date(2026, 1, 3), D(100), D(32), D("5")),
            Operacao(3, "PETR4", "venda", date(2026, 2, 2), D(50), D(40), D("3")),
        ]
    )
    (v,) = c.vendas
    # Preço médio (3000 + 5 + 3200 + 5) / 200 = 31,05.
    assert v.valor == D(2000) and v.custo_medio == D("1552.50") and v.resultado == D("444.50")


def test_calendario_bancario():
    assert pascoa(2026) == date(2026, 4, 5) and pascoa(2027) == date(2027, 3, 28)
    assert not dia_util_bancario(date(2026, 4, 3))  # Sexta-feira Santa
    assert not dia_util_bancario(date(2026, 2, 17))  # Carnaval
    assert not dia_util_bancario(date(2026, 6, 4))  # Corpus Christi
    assert ultimo_dia_util_do_mes_seguinte(date(2026, 1, 20)) == date(2026, 2, 27)
    assert ultimo_dia_util_do_mes_seguinte(date(2026, 11, 3)) == date(2026, 12, 30)


# API


@pytest.mark.db
def test_api_imposto(api):  # noqa: F811
    cid = nova_carteira(api)
    url = f"/v1/carteiras/{cid}/imposto"
    vazio = api.get(url, headers=auth()).json()
    assert vazio["meses"] == [] and vazio["codigo_darf"] == "6015"
    assert api.get(url, headers=auth("u2")).status_code == 404

    lancar(api, cid, data="2026-01-02", quantidade="1000", preco="30", custos="10")
    lancar(api, cid, tipo="venda", data="2026-02-03", quantidade="1000", preco="35", custos="10")
    lancar(api, cid, ticker="HGLG11", data="2026-03-02", quantidade="10", preco="100")
    lancar(api, cid, ticker="HGLG11", tipo="venda", data="2026-03-02", quantidade="10", preco="110")

    r = api.get(url, headers=auth())
    assert r.status_code == 200 and r.headers["cache-control"] == "private, no-store"
    dados = r.json()
    mar, fev = dados["meses"]
    # 35.000 − 10 − 30.010 = 4.980; vendas de 35 mil: tributa 15% = 747,00; IRRF 1,75.
    assert fev["mes"] == "2026-02-01" and fev["isento_acoes"] is False
    assert fev["resultado_acoes"] == "4980.00" and fev["imposto_devido"] == "747.00"
    assert fev["irrf"] == "1.75" and fev["darf"] == "745.25"
    assert fev["vencimento"] == "2026-03-31"
    # FII comprado e vendido no mesmo dia: day trade no grupo dos FIIs, 20% de 100 = 20,00,
    # menos o IRRF de 1% sobre o resultado do dia (1,00).
    assert mar["base_fii"] == "100.00" and mar["irrf"] == "1.00" and mar["darf"] == "19.00"
    assert dados["day_trade"] == [{"ticker": "HGLG11", "data": "2026-03-02"}]
    assert dados["anos"] == [
        {"ano": 2026, "ganho_isento": "0.00", "darf": "764.25", "vendas": "36100.00"}
    ]

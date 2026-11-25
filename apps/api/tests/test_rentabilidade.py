from datetime import date, timedelta
from decimal import Decimal as D

import pytest

from dominio.carteira import Operacao
from dominio.modelos import Provento
from dominio.rentabilidade import reduzir, serie_rentabilidade

D1, D2, D3, D4 = (date(2024, 3, 4) + timedelta(days=i) for i in range(4))


def op(i, tipo, dia, qtd, preco, ticker="PETR4"):
    return Operacao(i, ticker, tipo, dia, D(qtd), D(preco))


def precos(*valores, inicio=D1, ticker="PETR4"):
    return {ticker: {inicio + timedelta(days=i): D(v) for i, v in enumerate(valores)}}


def ultimo(serie):
    return round(serie[-1].carteira, 6)


def test_retorno_simples():
    s = serie_rentabilidade([op(1, "compra", D1, "10", "10")], {}, precos("10", "11", "12.1"))
    assert [round(p.carteira, 6) for p in s] == [0, 10, 21]
    assert s[-1].patrimonio == 121


def test_aporte_no_meio_nao_distorce():
    # 10 -> 11 (+10%), novo aporte a 11, depois 11 -> 9,9 (-10%): TWR = 1,1 × 0,9 - 1 = -1%.
    ops = [op(1, "compra", D1, "10", "10"), op(2, "compra", D2, "100", "11")]
    s = serie_rentabilidade(ops, {}, precos("10", "11", "9.9"))
    assert ultimo(s) == pytest.approx(-1.0)


def test_venda_e_recompra():
    ops = [
        op(1, "compra", D1, "10", "10"),
        op(2, "venda", D2, "10", "12"),  # +20% e carteira zerada
        op(3, "compra", D3, "5", "6"),
    ]
    s = serie_rentabilidade(ops, {}, precos("10", "12", "6", "6.6"))
    assert ultimo(s) == pytest.approx((1.2 * 1.1 - 1) * 100)


def test_proventos_contam_como_retorno():
    # Dividendo de 1 na data-com D2; o preço cai de 10 para 9 no dia seguinte (ex).
    prov = {"PETR4": [Provento("dividendo", D2, D("1"))]}
    s = serie_rentabilidade([op(1, "compra", D1, "10", "10")], prov, precos("10", "10", "9"))
    assert ultimo(s) == pytest.approx(0.0)


def test_desdobramento_com_precos_ajustados():
    # Desdobramento 1:2 na data-com D2. O banco guarda o histórico ajustado: 5, 5, 5.
    prov = {"PETR4": [Provento("desdobramento", D2, D("2"))]}
    s = serie_rentabilidade([op(1, "compra", D1, "10", "10")], prov, precos("5", "5", "5"))
    assert [p.patrimonio for p in s] == [100, 100, 100]
    assert ultimo(s) == 0


def test_cdi_e_ibov():
    cdi = {D1: 0.05, D2: 0.05, D3: 0.05}
    ibov = {D1: 100.0, D2: 110.0, D3: 99.0}
    s = serie_rentabilidade(
        [op(1, "compra", D1, "1", "10")], {}, precos("10", "10", "10"), cdi=cdi, ibov=ibov
    )
    assert s[0].cdi == 0 and s[-1].cdi == pytest.approx((1.0005**2 - 1) * 100)
    assert s[-1].ibov == pytest.approx(-1.0)


def test_sem_cotacao_usa_preco_da_compra():
    s = serie_rentabilidade([op(1, "compra", D4, "1", "10")], {}, precos("10", "10"))
    assert s[-1].data == D4 and s[-1].patrimonio == 10


def test_reduzir_mantem_ultimo_da_semana():
    s = serie_rentabilidade(
        [op(1, "compra", D1, "1", "10")],
        {},
        {"PETR4": {D1 + timedelta(days=i): D(10) for i in range(30)}},
    )
    r = reduzir(s, maximo=10)
    assert r[-1] == s[-1] and len(r) == 5 and all(p.data.weekday() == 6 for p in r[:-1])

from datetime import date
from decimal import Decimal as D

import pytest

from dominio.carteira import Operacao, VendaAcimaDaPosicao, alocacao, consolidar
from dominio.modelos import Provento


def op(i, tipo, dia, qtd, preco, custos="0", ticker="PETR4"):
    return Operacao(i, ticker, tipo, dia, D(qtd), D(preco), D(custos))


def test_preco_medio_com_compras_e_venda_parcial():
    c = consolidar(
        [
            op(1, "compra", date(2024, 1, 10), "100", "10", "5"),
            op(2, "compra", date(2024, 2, 10), "100", "12", "5"),
            op(3, "venda", date(2024, 3, 10), "50", "15", "4"),
        ]
    )
    p = c.posicoes["PETR4"]
    # PM = (1000 + 5 + 1200 + 5) / 200 = 11,05; a venda não muda o PM.
    assert p.quantidade == 150
    assert p.preco_medio == D("11.05")
    assert p.resultado_realizado == D("750") - D("4") - D("552.5")


def test_venda_total_zera_custo_e_recompra_comeca_do_zero():
    c = consolidar(
        [
            op(1, "compra", date(2024, 1, 10), "10", "10"),
            op(2, "venda", date(2024, 2, 10), "10", "20"),
            op(3, "compra", date(2024, 3, 10), "10", "30"),
        ]
    )
    p = c.posicoes["PETR4"]
    assert p.preco_medio == 30 and p.resultado_realizado == 100


def test_venda_acima_da_posicao_na_data():
    with pytest.raises(VendaAcimaDaPosicao) as e:
        consolidar(
            [
                op(1, "compra", date(2024, 1, 10), "10", "10"),
                op(2, "venda", date(2024, 1, 9), "5", "10"),  # antes da compra
            ]
        )
    assert e.value.disponivel == 0 and "09/01/2024" in str(e.value)


def test_compra_e_venda_no_mesmo_dia_seguem_a_ordem_de_lancamento():
    c = consolidar(
        [
            op(1, "compra", date(2024, 1, 10), "10", "10"),
            op(2, "venda", date(2024, 1, 10), "10", "11"),
        ]
    )
    assert c.posicoes["PETR4"].quantidade == 0


def test_desdobramento_e_grupamento_mantem_custo():
    eventos = {
        "PETR4": [
            Provento("desdobramento", date(2024, 2, 1), D("2")),
            Provento("grupamento", date(2024, 4, 1), D("0.1")),
        ]
    }
    ops = [
        op(1, "compra", date(2024, 1, 10), "100", "10"),
        op(2, "compra", date(2024, 3, 1), "100", "6"),
    ]
    c = consolidar(ops, eventos)
    p = c.posicoes["PETR4"]
    # 100 -> 200 no desdobramento, +100 = 300, grupamento 10:1 -> 30. Custo 1000 + 600.
    assert p.quantidade == 30 and p.custo == 1600
    assert p.preco_medio == D("1600") / 30


def test_evento_antes_da_primeira_compra_nao_conta():
    eventos = {"PETR4": [Provento("desdobramento", date(2023, 1, 1), D("2"))]}
    c = consolidar([op(1, "compra", date(2024, 1, 10), "10", "10")], eventos)
    assert c.posicoes["PETR4"].quantidade == 10


def test_proventos_pela_custodia_na_data_com():
    proventos = {
        "PETR4": [
            Provento(
                "dividendo", date(2024, 1, 10), D("0.5"), date(2024, 2, 20)
            ),  # compra no dia conta
            Provento("jcp", date(2024, 3, 15), D("0.25")),  # depois da venda parcial
            Provento("dividendo", date(2024, 6, 1), D("1")),  # depois da venda total
        ]
    }
    ops = [
        op(1, "compra", date(2024, 1, 10), "100", "10"),
        op(2, "venda", date(2024, 3, 15), "40", "11"),  # venda na data-com: sai antes
        op(3, "venda", date(2024, 5, 1), "60", "12"),
    ]
    c = consolidar(ops, proventos)
    assert [(p.tipo, p.quantidade, p.total) for p in c.proventos] == [
        ("dividendo", 100, D("50.00")),
        ("jcp", 60, D("15.00")),
    ]
    assert c.posicoes["PETR4"].proventos == D("65.00")
    assert c.abertas == []


def test_proventos_respeitam_data_limite():
    proventos = {"PETR4": [Provento("dividendo", date(2030, 1, 1), D("1"))]}
    c = consolidar(
        [op(1, "compra", date(2024, 1, 10), "10", "10")], proventos, ate=date(2025, 1, 1)
    )
    assert c.proventos == []


def test_varios_ativos_e_alocacao():
    c = consolidar(
        [
            op(1, "compra", date(2024, 1, 10), "10", "10", ticker="VALE3"),
            op(2, "compra", date(2024, 1, 10), "10", "10", ticker="PETR4"),
        ]
    )
    assert [p.ticker for p in c.abertas] == ["PETR4", "VALE3"]
    fatias = alocacao({"PETR4": D("300"), "VALE3": D("100"), "ZERO3": D("0")})
    assert [(f.chave, round(f.percentual)) for f in fatias] == [("PETR4", 75), ("VALE3", 25)]
    assert alocacao({}) == []

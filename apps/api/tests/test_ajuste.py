from datetime import date
from decimal import Decimal as D

from dominio.ajuste import ajustar_por_eventos, precisa_rebaixar_historico
from dominio.modelos import Candle, Provento


def c(dia, preco, vol=100):
    p = D(preco)
    return Candle(date(2025, 3, dia), p, p, p, p, p, vol)


def test_desdobramento_divide_precos_anteriores_e_multiplica_volume():
    evento = Provento("desdobramento", date(2025, 3, 4), D(2))
    saida = ajustar_por_eventos([c(3, 20), c(4, 20), c(5, 10)], [evento])
    assert [x.fechamento for x in saida] == [D(10), D(10), D(10)]
    assert [x.volume for x in saida] == [200, 200, 100]


def test_grupamento_multiplica_precos_anteriores():
    evento = Provento("grupamento", date(2025, 3, 3), D("0.1"))
    saida = ajustar_por_eventos([c(3, 1), c(4, 10)], [evento])
    assert [x.fechamento for x in saida] == [D(10), D(10)]
    assert saida[0].volume == 10


def test_dividendo_nao_ajusta_preco():
    evento = Provento("dividendo", date(2025, 3, 4), D("0.5"))
    assert ajustar_por_eventos([c(3, 20)], [evento]) == [c(3, 20)]


def test_precisa_rebaixar_historico():
    p = Provento("jcp", date(2025, 3, 4), D("0.5"))
    assert precisa_rebaixar_historico([p], date(2020, 1, 2))
    assert not precisa_rebaixar_historico([p], None)
    assert not precisa_rebaixar_historico([], date(2020, 1, 2))

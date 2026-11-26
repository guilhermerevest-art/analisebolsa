import pytest

from dominio import posicao as ps


def test_quantidade_pelo_risco_arredondada_no_lote():
    # Risco de 1% de 100 mil = R$ 1.000; stop a R$ 2 da entrada -> 500 ações.
    p = ps.calcular(100_000, 1, 30.0, 28.0, lote=100, concentracao_pct=100)
    assert p.quantidade == 500 and p.valor == 15_000 and p.perda_stop == 1000
    assert p.limitada_por is None
    assert p.alvos == [(1, 32.0), (2, 34.0), (3, 36.0)]
    # Stop a R$ 3 -> 333,3 ações: 300 no lote padrão, 333 no fracionário.
    assert ps.calcular(100_000, 1, 30.0, 27.0, concentracao_pct=100).quantidade == 300
    assert ps.calcular(100_000, 1, 30.0, 27.0, lote=1, concentracao_pct=100).quantidade == 333


def test_limite_de_concentracao_e_de_capital():
    p = ps.calcular(10_000, 2, 10.0, 9.9, lote=1, concentracao_pct=25)
    assert p.quantidade == 250 and p.limitada_por == "concentracao"
    assert p.pct_capital == pytest.approx(0.25)
    q = ps.calcular(10_000, 2, 10.0, 9.9, lote=1, concentracao_pct=100)
    assert q.quantidade == 1000 and q.limitada_por == "capital"


def test_capital_pequeno_para_o_lote_padrao():
    assert ps.calcular(2_000, 1, 30.0, 28.0).quantidade == 0


@pytest.mark.parametrize(("entrada", "stop"), [(30, 30), (30, 31), (30, 0)])
def test_stop_invalido(entrada, stop):
    with pytest.raises(ps.PosicaoInvalida):
        ps.calcular(10_000, 1, entrada, stop)


def test_stop_por_atr():
    assert ps.stop_por_atr(30.0, 1.25, 2) == 27.5


def test_aviso_sem_linguagem_de_recomendacao():
    from app.rotas.posicao import AVISO
    from tests.test_insights import PROIBIDAS

    assert not PROIBIDAS.search(AVISO.replace("Não é recomendação de investimento.", ""))

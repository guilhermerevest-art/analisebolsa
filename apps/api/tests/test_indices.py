import json
from datetime import date
from itertools import pairwise
from pathlib import Path

import pytest
from sqlalchemy import text

from fontes.bcb import janelas, parse
from fontes.yahoo import YahooFonte
from worker.indices import atualizar_indices

FIX = Path(__file__).parent / "fixtures"


def test_parse_cdi_do_sgs():
    pontos = parse(json.loads((FIX / "bcb_cdi_2024_10.json").read_text()))
    assert pontos[0] == (date(2024, 10, 1), 0.040168)
    assert len(pontos) == 8


def test_parse_ipca_do_sgs():
    pontos = parse(json.loads((FIX / "bcb_ipca_2024s1.json").read_text()))
    assert pontos[1] == (date(2024, 2, 1), 0.83)


def test_parse_rejeita_resposta_de_erro():
    with pytest.raises(Exception, match="inesperada"):
        parse({"error": "janela maior que 10 anos"})


def test_janelas_cobrem_o_periodo_sem_passar_de_10_anos():
    js = janelas(date(2005, 1, 1), date(2026, 11, 25))
    assert js[0][0] == date(2005, 1, 1) and js[-1][1] == date(2026, 11, 25)
    assert all((fim - ini).days < 3650 for ini, fim in js)
    assert all((b[0] - a[1]).days == 1 for a, b in pairwise(js))


def test_ibovespa_do_yahoo():
    r = json.loads((FIX / "yahoo_bvsp_2024_10.json").read_text())["chart"]["result"][0]
    candles = YahooFonte.parse_cotacoes(r, date(2024, 10, 1), date(2024, 10, 10))
    assert candles[0].data == date(2024, 10, 1)
    assert float(candles[0].fechamento) == 132495.0


@pytest.mark.db
def test_atualizar_indices_continua_e_isola_falhas(db):
    chamadas = []

    def cdi(i, f):
        chamadas.append(("cdi", i, f))
        return [(date(2024, 10, 1), 0.04), (date(2024, 10, 2), 0.041)]

    def falha(i, f):
        raise RuntimeError("fora do ar")

    fontes = {"cdi": cdi, "ipca": lambda i, f: [(date(2024, 9, 1), 0.44)], "ibov": falha}
    res = atualizar_indices(db, date(2024, 10, 2), desde=date(2024, 1, 1), fontes=fontes)
    assert res["cdi"] == 2 and res["ipca"] == 1 and res["ibov"].startswith("erro")
    assert chamadas[0][1] == date(2024, 1, 1)

    # Segunda rodada recomeça perto da última data e não duplica.
    atualizar_indices(db, date(2024, 10, 3), fontes=fontes)
    assert chamadas[1][1] == date(2024, 9, 27)
    with db.connect() as conn:
        n = conn.execute(text("SELECT count(*) FROM indices WHERE serie = 'cdi'")).scalar_one()
    assert n == 2

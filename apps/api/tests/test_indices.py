import json
from datetime import date, timedelta
from itertools import pairwise
from pathlib import Path

import pytest
from sqlalchemy import text

from fontes.bcb import janelas, parse
from fontes.yahoo import YahooFonte
from tests.test_api import cliente  # noqa: F401 (fixture)
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


def test_ifix_da_b3():
    from fontes.b3 import parse_ano

    dados = json.loads((FIX / "b3_ifix_2025.json").read_text())
    pontos = parse_ano(dados, 2025)
    assert pontos == sorted(pontos) and len(pontos) > 240  # pregões do ano
    assert all(d.year == 2025 for d, _ in pontos)
    assert all(2500 < v < 4500 for _, v in pontos)
    # 30/02 e afins não viram data; ano antes de o índice existir vem vazio.
    assert parse_ano({"min": None, "max": None, "results": None}, 2009) == []
    with pytest.raises(Exception, match="inesperada"):
        parse_ano({"erro": "x"}, 2025)


def test_b3_um_ano_por_consulta_e_recorte_do_periodo():
    from fontes.b3 import B3IndicesFonte

    class Http:
        def __init__(self):
            self.urls = []

        def get_json(self, url, **kw):
            self.urls.append(url)
            return 200, {
                "results": [{"day": 2, **{f"rateValue{m}": "1.000,50" for m in range(1, 13)}}]
            }

    http = Http()
    pontos = B3IndicesFonte(http).serie("IFIX", date(2024, 3, 1), date(2025, 2, 10))
    assert len(http.urls) == 2  # 2024 e 2025
    assert pontos[0] == (date(2024, 3, 2), 1000.5) and pontos[-1] == (date(2025, 2, 2), 1000.5)
    assert len(pontos) == 10 + 2


@pytest.mark.db
def test_api_indicadores_de_mercado(cliente, db):  # noqa: F811
    hoje = date.today()
    with db.begin() as conn:
        conn.execute(
            text("INSERT INTO indices (serie, data, valor) VALUES (:s, :d, :v)"),
            [
                {"s": "dolar", "d": date(hoje.year - 1, 12, 31), "v": 5.0},
                {"s": "dolar", "d": hoje - timedelta(days=1), "v": 5.4},
                {"s": "dolar", "d": hoje, "v": 5.5},
                {"s": "ifix", "d": hoje, "v": 3500.0},
            ],
        )
    r = cliente.get("/v1/mercado/indicadores")
    assert r.status_code == 200, r.text
    itens = {i["serie"]: i for i in r.json()["itens"]}
    assert list(itens) == ["ifix", "dolar"]  # na ordem da página; sem dados, a série some
    dolar = itens["dolar"]
    assert dolar["nome"] == "Dólar" and dolar["unidade"] == "reais" and dolar["valor"] == 5.5
    assert round(dolar["var_ano"], 2) == 10.0
    assert round(dolar["var_dia"], 2) == round((5.5 / 5.4 - 1) * 100, 2)
    assert itens["ifix"]["var_dia"] is None

    r = cliente.get("/v1/indices/dolar")
    assert r.json()["unidade"] == "reais" and r.json()["pontos"][-1]["valor"] == 5.5
    assert cliente.get("/v1/indices/xpto").status_code == 422

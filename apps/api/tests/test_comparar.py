from datetime import date, timedelta

import pytest

from tests.test_api import cliente, cliente_screener, token  # noqa: F401 (fixtures)


@pytest.mark.db
def test_comparar_base_100_e_metricas(cliente_screener):  # noqa: F811
    api = cliente_screener
    inicio = (date.today() - timedelta(days=3650)).isoformat()
    r = api.get(f"/v1/comparar?tickers=petr4, VALE3,PETR4&inicio={inicio}")
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "public, max-age=3600"
    dados = r.json()
    assert [a["ticker"] for a in dados["ativos"]] == ["PETR4", "VALE3"]  # sem repetir
    petr, vale = dados["series"]
    # As duas séries começam juntas, no primeiro dia em que ambas têm cotação, em 100.
    assert petr["pontos"][0]["data"] == vale["pontos"][0]["data"] == dados["inicio"]
    assert petr["pontos"][0]["valor"] == vale["pontos"][0]["valor"] == 100
    assert dados["ativos"][0]["preco"] is not None


@pytest.mark.db
def test_comparar_validacao(cliente):  # noqa: F811
    assert cliente.get("/v1/comparar?tickers=PETR4").status_code == 422
    assert cliente.get("/v1/comparar?tickers=A1,B2,C3,D4,E5").status_code == 422
    r = cliente.get("/v1/comparar?tickers=PETR4,ZZZZ3")
    assert r.status_code == 404 and "ZZZZ3" in r.json()["detail"]
    # Ativo sem métricas calculadas ainda aparece, com os campos vazios.
    r = cliente.get("/v1/comparar?tickers=PETR4,HGLG11")
    assert r.status_code == 200 and r.json()["ativos"][1]["preco"] is None

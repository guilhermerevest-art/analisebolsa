import pytest
from sqlalchemy import text

from tests.test_api import cliente  # noqa: F401 (fixture)


@pytest.mark.db
def test_simulador_com_ativo(cliente, db):  # noqa: F811
    with db.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO indices VALUES ('cdi','2024-03-04',0.04),('cdi','2024-03-05',0.04),"
                "('ipca','2024-03-01',0.5)"
            )
        )
    r = cliente.get(
        "/v1/simulador",
        params={
            "ticker": "petr4",
            "inicio": "2024-03-01",
            "aporte_inicial": 1000,
            "aporte_mensal": 100,
        },
    )
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "public, max-age=3600"
    corpo = r.json()
    assert corpo["ticker"] == "PETR4" and corpo["inicio"] == "2024-03-01"
    primeiro = corpo["pontos"][0]
    assert primeiro["aportado"] == 1100 and primeiro["patrimonio"] > 0
    assert primeiro["cdi"] == pytest.approx(1100 * 1.0004**2, abs=0.01)
    assert corpo["pontos"][1]["ipca"] == pytest.approx(1105.5 + 100)
    assert corpo["ipca_ate"] == "2024-03-01"
    assert corpo["faixa"] is None  # menos de 5 anos de histórico
    assert "não garante" in corpo["aviso"]


@pytest.mark.db
def test_simulador_sem_ativo_e_validacoes(cliente, db):  # noqa: F811
    with db.begin() as conn:
        conn.execute(text("INSERT INTO indices VALUES ('cdi','2024-03-04',0.04)"))
    r = cliente.get("/v1/simulador", params={"inicio": "2024-03-01", "aporte_mensal": 50})
    assert r.status_code == 200
    (ponto,) = r.json()["pontos"]
    assert ponto["cdi"] == 50 and ponto["patrimonio"] is None

    base = {"inicio": "2024-03-01", "aporte_mensal": 50}
    assert cliente.get("/v1/simulador", params={"inicio": "2024-03-01"}).status_code == 422
    assert cliente.get("/v1/simulador", params=base | {"inicio": "2004-12-31"}).status_code == 422
    assert cliente.get("/v1/simulador", params=base | {"ticker": "X!"}).status_code == 422
    assert cliente.get("/v1/simulador", params=base | {"ticker": "ABCD3"}).status_code == 404

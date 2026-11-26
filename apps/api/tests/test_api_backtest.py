import pytest
from sqlalchemy import text

from tests.test_api import cliente  # noqa: F401 (fixture)

BASE = {"ticker": "petr4", "inicio": "2024-01-01"}


@pytest.mark.db
def test_backtest_cruzamento(cliente, db):  # noqa: F811
    with db.begin() as conn:
        conn.execute(text("INSERT INTO indices VALUES ('cdi','2024-06-03',0.04)"))
    r = cliente.get(
        "/v1/backtest",
        params=BASE | {"estrategia": "cruzamento_mm", "curta": 5, "longa": 20, "stop_atr": 2},
    )
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "public, max-age=3600"
    corpo = r.json()
    assert corpo["ticker"] == "PETR4" and corpo["parametros"] == {"curta": 5, "longa": 20}
    assert corpo["custos"]["taxas"] == pytest.approx(0.0003)
    assert corpo["inicio"] > "2024-01-01"  # aquecimento sem histórico anterior
    assert corpo["inicio"] < corpo["divisao"] < corpo["fim"]
    assert corpo["pontos"][-1]["data"] == corpo["fim"]
    assert set(corpo["total"]) == {"estrategia", "buy_and_hold", "cdi"}
    assert corpo["total"]["estrategia"]["operacoes"] == len(corpo["operacoes"])
    assert "não garante" in corpo["aviso"]


@pytest.mark.db
def test_backtest_validacoes(cliente):  # noqa: F811
    rsi = BASE | {"estrategia": "rsi"}
    assert cliente.get("/v1/backtest", params=rsi).status_code == 200
    casos = [
        (BASE | {"estrategia": "xyz"}, 422),
        (rsi | {"rsi_entrada": 70}, 422),
        (BASE | {"estrategia": "cruzamento_mm", "curta": 50, "longa": 30}, 422),
        (rsi | {"inicio": "2004-12-31"}, 422),
        (rsi | {"fim": "2024-01-01"}, 422),
        (rsi | {"inicio": "2025-12-01"}, 422),  # menos de um ano de pregões
        (rsi | {"ticker": "X!"}, 422),
        (rsi | {"ticker": "ABCD3"}, 404),
        (rsi | {"stop_atr": 9}, 422),
    ]
    for params, status in casos:
        r = cliente.get("/v1/backtest", params=params)
        assert r.status_code == status, (params, r.text)

import pytest
from sqlalchemy import text

from tests.test_api import cliente  # noqa: F401 (fixture)


@pytest.mark.db
def test_posicao_manual(cliente):  # noqa: F811
    r = cliente.get("/v1/posicao", params={"capital": 100000, "entrada": 30, "stop": 28})
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "public, max-age=3600"
    corpo = r.json()
    assert corpo["quantidade"] == 500 and corpo["perda_stop"] == 1000
    assert corpo["ativo"] is None and corpo["limitada_por"] is None
    assert [a["preco"] for a in corpo["alvos"]] == [32, 34, 36]
    assert "não diz o que operar" in corpo["aviso"]


@pytest.mark.db
def test_posicao_com_ativo_e_atr(cliente, db):  # noqa: F811
    with db.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO indicadores_diarios (ativo_id, data, atr14) "
                "SELECT ativo_id, max(data), 1.5 FROM cotacoes_diarias "
                "JOIN ativos USING (ativo_id) WHERE ticker = 'PETR4' GROUP BY ativo_id"
            )
        )
    r = cliente.get(
        "/v1/posicao", params={"capital": 50000, "ticker": "petr4", "atr_mult": 2, "lote": 1}
    )
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["ativo"]["ticker"] == "PETR4" and corpo["ativo"]["atr14"] == 1.5
    assert corpo["entrada"] == corpo["ativo"]["fechamento"]
    assert corpo["stop"] == pytest.approx(corpo["entrada"] - 3, abs=0.01)


@pytest.mark.db
def test_posicao_validacoes(cliente):  # noqa: F811
    casos = [
        ({"capital": 1000, "entrada": 30}, 422),  # sem stop nem ATR
        ({"capital": 1000, "entrada": 30, "stop": 31}, 422),
        ({"capital": 1000}, 422),
        ({"capital": 1000, "entrada": 30, "stop": 28, "risco": 9}, 422),
        ({"capital": 1000, "entrada": 30, "stop": 28, "lote": 10}, 422),
        ({"capital": 1000, "ticker": "ABCD3", "atr_mult": 2}, 404),
    ]
    for params, status in casos:
        assert cliente.get("/v1/posicao", params=params).status_code == status, params

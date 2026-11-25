from datetime import date

import pytest
from sqlalchemy import text

from tests.test_api import cliente, token  # noqa: F401 (fixture)


def auth(sub="u1"):
    return {"Authorization": f"Bearer {token(sub=sub)}"}


@pytest.fixture
def usuarios(cliente, db):  # noqa: F811
    with db.begin() as conn:
        conn.execute(
            text("INSERT INTO users (id, email) VALUES ('u1', 'a@x.com'), ('u2', 'b@x.com')")
        )
    return cliente


@pytest.mark.db
def test_watchlist_exige_login(usuarios):
    assert usuarios.get("/v1/watchlist").status_code == 401
    assert usuarios.put("/v1/watchlist/PETR4").status_code == 401


@pytest.mark.db
def test_watchlist_adiciona_lista_e_remove(usuarios):
    assert usuarios.get("/v1/watchlist/PETR4", headers=auth()).json()["na_lista"] is False
    r = usuarios.put("/v1/watchlist/petr4", headers=auth())
    assert r.status_code == 200 and r.json() == {"ticker": "PETR4", "na_lista": True}
    assert usuarios.put("/v1/watchlist/PETR4", headers=auth()).status_code == 200  # idempotente
    usuarios.put("/v1/watchlist/HGLG11", headers=auth())

    r = usuarios.get("/v1/watchlist", headers=auth())
    assert r.headers["cache-control"] == "private, no-store"
    corpo = r.json()
    assert [i["ticker"] for i in corpo["itens"]] == ["HGLG11", "PETR4"]
    assert corpo["itens"][0]["metricas"] is None  # sem métricas calculadas
    assert corpo["limite"] == 100

    usuarios.delete("/v1/watchlist/PETR4", headers=auth())
    assert [i["ticker"] for i in usuarios.get("/v1/watchlist", headers=auth()).json()["itens"]] == [
        "HGLG11"
    ]


@pytest.mark.db
def test_watchlist_isolada_por_usuario(usuarios):
    usuarios.put("/v1/watchlist/PETR4", headers=auth("u1"))
    assert usuarios.get("/v1/watchlist", headers=auth("u2")).json()["itens"] == []
    usuarios.delete("/v1/watchlist/PETR4", headers=auth("u2"))
    assert len(usuarios.get("/v1/watchlist", headers=auth("u1")).json()["itens"]) == 1


@pytest.mark.db
def test_watchlist_ticker_inexistente_e_usuario_sem_cadastro(usuarios):
    assert usuarios.put("/v1/watchlist/XXXX3", headers=auth()).status_code == 404
    assert usuarios.put("/v1/watchlist/PETR4", headers=auth("fantasma")).status_code == 401


@pytest.mark.db
def test_watchlist_limite(usuarios, db, monkeypatch):
    from app import usuario

    monkeypatch.setattr(usuario, "LIMITE_WATCHLIST", 2)
    usuarios.put("/v1/watchlist/PETR4", headers=auth())
    usuarios.put("/v1/watchlist/PETR3", headers=auth())
    r = usuarios.put("/v1/watchlist/VALE3", headers=auth())
    assert r.status_code == 409 and "até 2 ativos" in r.json()["detail"]


@pytest.mark.db
def test_excluir_usuario_apaga_watchlist(usuarios, db):
    usuarios.put("/v1/watchlist/PETR4", headers=auth())
    with db.begin() as conn:
        conn.execute(text("DELETE FROM users WHERE id = 'u1'"))
        assert conn.execute(text("SELECT count(*) FROM watchlist")).scalar_one() == 0


@pytest.mark.db
def test_indices(usuarios, db):
    with db.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO indices VALUES ('cdi','2024-10-01',0.04),('cdi','2024-10-02',0.041),"
                "('ibov','2024-10-01',132495)"
            )
        )
    r = usuarios.get("/v1/indices/cdi", params={"inicio": "2024-01-01", "fim": "2024-12-31"})
    assert r.json() == {
        "serie": "cdi",
        "unidade": "pct_dia",
        "pontos": [{"data": "2024-10-01", "valor": 0.04}, {"data": "2024-10-02", "valor": 0.041}],
    }
    assert usuarios.get("/v1/indices/selic").status_code == 422
    assert (
        usuarios.get(
            "/v1/indices/cdi", params={"inicio": date(2025, 1, 2), "fim": date(2025, 1, 1)}
        ).status_code
        == 422
    )

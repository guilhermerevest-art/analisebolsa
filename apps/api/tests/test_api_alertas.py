import pytest
from sqlalchemy import text

from tests.test_api import cliente, token  # noqa: F401 (fixture)
from tests.test_api_carteira import api, auth, lancar, nova_carteira  # noqa: F401


def criar(api, sub="u1", **campos):  # noqa: F811
    corpo = {"ticker": "PETR4", "tipo": "preco_acima", "parametro": 40} | campos
    return api.post("/v1/alertas", json=corpo, headers=auth(sub))


@pytest.mark.db
def test_alertas_crud_isolamento_e_validacao(api):  # noqa: F811
    assert api.get("/v1/alertas").status_code == 401
    r = criar(api)
    assert r.status_code == 201, r.text
    alerta = r.json()
    assert alerta["descricao"] == "Fechamento acima de R$ 40,00" and alerta["ativo"]

    sinal = criar(api, tipo="insight", codigo="maxima_52s", parametro=None).json()
    assert sinal["parametro"] is None and sinal["descricao"].startswith("Sinal:")

    lista = api.get("/v1/alertas", headers=auth()).json()
    assert lista["ligados"] == 2 and lista["limite"] == 30 and len(lista["sinais"]) == 11
    assert api.get("/v1/alertas", headers=auth("u2")).json()["itens"] == []

    caminho = f"/v1/alertas/{alerta['id']}"
    assert api.patch(caminho, json={"ativo": False}, headers=auth("u2")).status_code == 404
    assert api.delete(caminho, headers=auth("u2")).status_code == 404
    assert api.patch(caminho, json={"ativo": False}, headers=auth()).json()["ativo"] is False
    assert api.delete(caminho, headers=auth()).status_code == 204
    assert api.delete(caminho, headers=auth()).status_code == 404

    assert criar(api, parametro=None).status_code == 422
    assert criar(api, tipo="variacao_dia", parametro=150).status_code == 422
    assert criar(api, tipo="insight", codigo="nao_existe").status_code == 422
    assert criar(api, ticker="ZZZZ3").status_code == 404


@pytest.mark.db
def test_limite_de_alertas_ligados(api, monkeypatch):  # noqa: F811
    from app import alertas

    monkeypatch.setattr(alertas, "LIMITE_ALERTAS", 1)
    primeiro = criar(api).json()
    assert criar(api).status_code == 409
    api.patch(f"/v1/alertas/{primeiro['id']}", json={"ativo": False}, headers=auth())
    segundo = criar(api).json()
    r = api.patch(f"/v1/alertas/{primeiro['id']}", json={"ativo": True}, headers=auth())
    assert r.status_code == 409 and segundo["ativo"]


@pytest.mark.db
def test_exportar_e_excluir_conta_em_cascata(api, db):  # noqa: F811
    cid = nova_carteira(api)
    lancar(api, cid)
    criar(api)
    api.put("/v1/watchlist/PETR4", headers=auth())

    r = api.get("/v1/conta/exportar", headers=auth())
    assert r.status_code == 200 and r.headers["cache-control"] == "private, no-store"
    dados = r.json()
    assert dados["usuario"]["email"] == "a@x.com"
    assert dados["watchlist"][0]["ticker"] == "PETR4"
    assert dados["carteiras"][0]["operacoes"][0]["ticker"] == "PETR4"
    assert len(dados["alertas"]) == 1
    assert "password_hash" not in str(dados)

    assert api.delete("/v1/conta", headers=auth()).status_code == 204
    with db.connect() as conn:
        for tabela in ("users", "carteiras", "operacoes", "alertas", "watchlist"):
            n = conn.execute(text(f"SELECT count(*) FROM {tabela}")).scalar()
            assert n == (1 if tabela == "users" else 0), tabela  # sobra o u2
    assert api.get("/v1/conta/exportar", headers=auth()).status_code == 401

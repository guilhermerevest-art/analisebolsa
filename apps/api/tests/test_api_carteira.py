from datetime import date, timedelta

import pytest
from sqlalchemy import text

from tests.test_api import cliente, token  # noqa: F401 (fixture)


def auth(sub="u1"):
    return {"Authorization": f"Bearer {token(sub=sub)}"}


@pytest.fixture
def api(cliente, db):  # noqa: F811
    with db.begin() as conn:
        conn.execute(
            text("INSERT INTO users (id, email) VALUES ('u1', 'a@x.com'), ('u2', 'b@x.com')")
        )
    return cliente


def nova_carteira(api, nome="Principal", sub="u1"):
    r = api.post("/v1/carteiras", json={"nome": nome}, headers=auth(sub))
    assert r.status_code == 201, r.text
    return r.json()["id"]


def lancar(api, cid, sub="u1", **campos):
    corpo = {
        "ticker": "PETR4",
        "tipo": "compra",
        "data": "2024-03-01",
        "quantidade": "100",
        "preco": "30",
        "custos": "0",
    } | campos
    return api.post(f"/v1/carteiras/{cid}/operacoes", json=corpo, headers=auth(sub))


@pytest.mark.db
def test_carteiras_exigem_login_e_sao_isoladas(api):
    assert api.get("/v1/carteiras").status_code == 401
    cid = nova_carteira(api)
    assert api.get("/v1/carteiras", headers=auth("u2")).json()["itens"] == []
    for metodo, caminho in [
        ("get", f"/v1/carteiras/{cid}/resumo"),
        ("get", f"/v1/carteiras/{cid}/operacoes"),
        ("delete", f"/v1/carteiras/{cid}"),
    ]:
        assert getattr(api, metodo)(caminho, headers=auth("u2")).status_code == 404
    assert lancar(api, cid, sub="u2").status_code == 404
    assert (
        api.patch(f"/v1/carteiras/{cid}", json={"nome": "x"}, headers=auth("u2")).status_code == 404
    )


@pytest.mark.db
def test_criar_renomear_excluir_e_limite(api, monkeypatch):
    from app import carteira

    cid = nova_carteira(api)
    r = api.patch(f"/v1/carteiras/{cid}", json={"nome": "  Dividendos "}, headers=auth())
    assert r.json()["nome"] == "Dividendos"
    assert api.post("/v1/carteiras", json={"nome": ""}, headers=auth()).status_code == 422
    monkeypatch.setattr(carteira, "LIMITE_CARTEIRAS", 1)
    assert api.post("/v1/carteiras", json={"nome": "Outra"}, headers=auth()).status_code == 409
    assert api.delete(f"/v1/carteiras/{cid}", headers=auth()).status_code == 204
    assert api.get("/v1/carteiras", headers=auth()).json()["itens"] == []


@pytest.mark.db
def test_operacoes_validam_posicao_ticker_e_data(api):
    cid = nova_carteira(api)
    r = lancar(api, cid, tipo="venda")
    assert r.status_code == 422 and "posição nessa data era de 0" in r.json()["detail"]
    assert lancar(api, cid, ticker="XXXX3").status_code == 422
    futuro = (date.today() + timedelta(days=2)).isoformat()
    assert lancar(api, cid, data=futuro).status_code == 422
    assert lancar(api, cid, quantidade="0").status_code == 422

    compra = lancar(api, cid, ticker="petr4").json()
    assert compra["ticker"] == "PETR4" and compra["quantidade"] == "100"
    venda = lancar(api, cid, tipo="venda", data="2024-04-01", quantidade="60", preco="35").json()

    # Apagar ou reduzir a compra deixaria a venda acima da posição: recusado.
    assert (
        api.delete(f"/v1/carteiras/{cid}/operacoes/{compra['id']}", headers=auth()).status_code
        == 422
    )
    corpo = {
        "ticker": "PETR4",
        "tipo": "compra",
        "data": "2024-03-01",
        "quantidade": "50",
        "preco": "30",
    }
    r = api.put(f"/v1/carteiras/{cid}/operacoes/{compra['id']}", json=corpo, headers=auth())
    assert r.status_code == 422
    ops = api.get(f"/v1/carteiras/{cid}/operacoes", headers=auth()).json()["itens"]
    assert [o["quantidade"] for o in ops] == ["60", "100"]  # nada mudou

    assert (
        api.delete(f"/v1/carteiras/{cid}/operacoes/{venda['id']}", headers=auth()).status_code
        == 204
    )
    assert (
        api.delete(f"/v1/carteiras/{cid}/operacoes/{compra['id']}", headers=auth()).status_code
        == 204
    )


@pytest.mark.db
def test_resumo(api):
    cid = nova_carteira(api)
    # PETR4 tem fechamento constante na fixture; HGLG11 não tem cotação.
    lancar(api, cid, data="2024-03-01", quantidade="100", preco="10", custos="10")
    lancar(api, cid, tipo="venda", data="2024-06-03", quantidade="40", preco="12", custos="2")
    lancar(api, cid, ticker="HGLG11", data="2024-03-01", quantidade="5", preco="160")
    r = api.get(f"/v1/carteiras/{cid}/resumo", headers=auth())
    assert r.status_code == 200 and r.headers["cache-control"] == "private, no-store"
    corpo = r.json()
    petr = next(p for p in corpo["posicoes"] if p["ticker"] == "PETR4")
    hglg = next(p for p in corpo["posicoes"] if p["ticker"] == "HGLG11")
    assert (
        petr["quantidade"] == "60" and petr["preco_medio"] == "10.10" and petr["custo"] == "606.00"
    )
    assert hglg["valor_atual"] is None and hglg["resultado"] is None
    # Venda: 480 - 2 - 40 × 10,10 = 74. Proventos pela custódia na data-com (mais novo primeiro).
    assert corpo["totais"]["resultado_realizado"] == "74.00"
    assert [(p["tipo"], p["quantidade"], p["total"]) for p in corpo["proventos"]] == [
        ("dividendo", "60", "60.00"),
        ("jcp", "60", "30.00"),
        ("dividendo", "100", "150.00"),
    ]
    preco = petr["preco_atual"]
    assert corpo["totais"]["patrimonio"] == f"{60 * float(preco):.2f}"
    assert [f["chave"] for f in corpo["alocacao"]["ativo"]] == ["PETR4"]
    assert corpo["alocacao"]["tipo"][0]["chave"] == "Ações"
    assert corpo["alocacao"]["setor"][0]["chave"] == "Energia"


@pytest.mark.db
def test_excluir_usuario_apaga_carteiras(api, db):
    cid = nova_carteira(api)
    lancar(api, cid)
    with db.begin() as conn:
        conn.execute(text("DELETE FROM users WHERE id = 'u1'"))
        assert conn.execute(text("SELECT count(*) FROM operacoes")).scalar_one() == 0

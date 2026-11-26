import io
import zipfile
from datetime import date

import pytest
from sqlalchemy import text

from fontes.cvm import parse_mes
from tests.test_api import cliente, token  # noqa: F401 (fixture)
from tests.test_api_carteira import api, auth, nova_carteira  # noqa: F401 (fixture)
from worker.fundos import atualizar_fundos

CNPJ = "00.017.024/0001-53"


def cdb(**campos):
    return {
        "tipo": "cdb",
        "nome": "CDB Banco X",
        "indexador": "cdi",
        "taxa": "110",
        "data_aplicacao": "2024-01-02",
        "valor_aplicado": "10000",
        "vencimento": "2027-01-04",
    } | campos


@pytest.mark.db
def test_crud_e_isolamento(api):  # noqa: F811
    cid = nova_carteira(api)
    url = f"/v1/carteiras/{cid}/investimentos"
    assert api.get(url).status_code == 401
    r = api.post(url, json=cdb(), headers=auth())
    assert r.status_code == 201, r.text
    iid = r.json()["id"]
    assert api.get(url, headers=auth("u2")).status_code == 404
    assert api.post(url, json=cdb(), headers=auth("u2")).status_code == 404
    assert api.delete(f"{url}/{iid}", headers=auth("u2")).status_code == 404

    lista = api.get(url, headers=auth()).json()
    item = lista["itens"][0]
    assert item["nome"] == "CDB Banco X" and item["descricao_taxa"] == "110% do CDI"
    assert lista["totais"]["aplicado"] == 10000

    r = api.put(f"{url}/{iid}", json=cdb(nome="CDB Y", taxa="100"), headers=auth())
    assert r.status_code == 204, r.text
    assert api.get(url, headers=auth()).json()["itens"][0]["nome"] == "CDB Y"
    assert api.delete(f"{url}/{iid}", headers=auth()).status_code == 204
    assert api.get(url, headers=auth()).json()["itens"] == []


@pytest.mark.db
def test_validacoes(api):  # noqa: F811
    cid = nova_carteira(api)
    url = f"/v1/carteiras/{cid}/investimentos"
    ruins = [
        cdb(data_aplicacao="2999-01-01"),
        cdb(vencimento="2023-01-01"),
        cdb(taxa="500"),
        cdb(indexador=None),
        cdb(resgate_data="2024-05-01"),
        {
            "tipo": "fundo",
            "nome": "Fundo",
            "data_aplicacao": "2024-01-02",
            "valor_aplicado": "1000",
        },
        {
            "tipo": "fundo",
            "nome": "Fundo",
            "cnpj": "11.111.111/1111-11",
            "data_aplicacao": "2024-01-02",
            "valor_aplicado": "1000",
        },
    ]
    for corpo in ruins:
        assert api.post(url, json=corpo, headers=auth()).status_code == 422, corpo
    r = api.post(url, json=cdb(tipo="lci_lca", isento_ir=False), headers=auth())
    assert r.status_code == 201
    assert api.get(url, headers=auth()).json()["itens"][0]["isento_ir"] is True


def zip_cvm(linhas: list[str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        corpo = "TP_FUNDO_CLASSE;CNPJ_FUNDO_CLASSE;ID_SUBCLASSE;DT_COMPTC;VL_TOTAL;VL_QUOTA\n"
        z.writestr("inf.csv", corpo + "\n".join(linhas))
    return buf.getvalue()


def test_parse_da_cvm_filtra_os_cnpjs():
    conteudo = zip_cvm(
        [
            f"FI;{CNPJ};;2024-03-04;1;10.5",
            f"FI;{CNPJ};;2024-03-05;1;10.6",
            "FI;11.222.333/0001-81;;2024-03-04;1;99",
        ]
    )
    assert parse_mes(conteudo, {"00017024000153"}) == [
        ("00017024000153", date(2024, 3, 4), 10.5),
        ("00017024000153", date(2024, 3, 5), 10.6),
    ]


@pytest.mark.db
def test_fundo_aguarda_e_depois_usa_as_cotas(api, db):  # noqa: F811
    cid = nova_carteira(api)
    url = f"/v1/carteiras/{cid}/investimentos"
    corpo = {
        "tipo": "fundo",
        "nome": "Fundo DI",
        "cnpj": CNPJ,
        "data_aplicacao": "2024-03-04",
        "valor_aplicado": "1000",
    }
    assert api.post(url, json=corpo, headers=auth()).status_code == 201
    item = api.get(url, headers=auth()).json()["itens"][0]
    assert item["bruto"] is None and "CVM" in item["observacao"]

    class Fonte:
        def __init__(self):
            self.meses = []

        def mes(self, ano, mes, cnpjs):
            self.meses.append((ano, mes))
            if (ano, mes) == (2024, 3):
                return [("00017024000153", date(2024, 3, 4), 10.0)]
            if (ano, mes) == (2024, 5):
                return [("00017024000153", date(2024, 5, 31), 11.0)]
            return []

    fonte = Fonte()
    res = atualizar_fundos(db, date(2024, 6, 10), fonte)
    assert res["cotas"] == 2 and fonte.meses == [(2024, 3), (2024, 4), (2024, 5), (2024, 6)]
    item = api.get(url, headers=auth()).json()["itens"][0]
    assert item["bruto"] == 1100.0 and item["cotas"] == 100.0
    # Na segunda vez, só os meses sem cota e os dois mais recentes.
    fonte.meses.clear()
    atualizar_fundos(db, date(2024, 6, 10), fonte)
    assert fonte.meses == [(2024, 4), (2024, 5), (2024, 6)]
    with db.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM cotas_fundos")).scalar_one() == 2

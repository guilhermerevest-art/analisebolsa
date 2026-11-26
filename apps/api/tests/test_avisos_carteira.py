from datetime import date

import pytest
from sqlalchemy import text

from app.notificacao import Canais
from dominio import avisos_carteira as av
from tests.test_alertas import PROIBIDAS, PushFalso
from tests.test_api import cliente, token  # noqa: F401 (fixture)
from tests.test_api_carteira import api, auth, lancar, nova_carteira  # noqa: F401 (fixture)
from worker.avisos_carteira import enviar_avisos, gerar_avisos


class EvolutionFalso:
    def __init__(self):
        self.enviados = []

    def enviar_texto(self, telefone, texto):
        self.enviados.append((telefone, texto))


def test_textos_dos_avisos():
    avisos = [
        av.provento_pago(
            1, "Principal", "PETR4", "dividendo", date(2024, 5, 2), date(2024, 6, 1), 1500
        ),
        av.data_com("PETR4", "jcp", date(2024, 6, 5), 0.25, date(2024, 7, 1)),
        av.darf(1, "Principal", date(2024, 5, 1), 748.25, date(2024, 6, 28)),
        av.vencimento(1, "Principal", 9, "CDB X", date(2024, 6, 7)),
    ]
    assert (
        avisos[0].texto
        == "PETR4 paga R$ 1.500,00 de dividendos em 01/06/2024 (carteira Principal)."
    )
    assert "recebe R$ 0,25 por cota de JCP, pagos em 01/07/2024" in avisos[1].texto
    assert avisos[2].texto.startswith(
        "O DARF de R$ 748,25 da carteira Principal (ganhos de 05/2024)"
    )
    textos = [a.texto for a in avisos] + [
        *av.compor_push(avisos).values(),
        av.compor_whatsapp(avisos, "https://s/carteira").replace(av.AVISO, ""),
    ]
    for t in textos:
        assert not PROIBIDAS.search(t), t
    assert av.compor_push(avisos[:1])["url"] == "/carteira?c=1"


@pytest.mark.db
def test_gera_uma_vez_respeita_preferencias_e_envia(api, db):  # noqa: F811
    cid = nova_carteira(api)
    assert lancar(api, cid, data="2024-03-01", quantidade="1000", preco="30").status_code == 201
    r = lancar(api, cid, tipo="venda", data="2024-05-10", quantidade="1000", preco="35")
    assert r.status_code == 201, r.text
    assert lancar(api, cid, data="2024-05-20", quantidade="100", preco="30").status_code == 201
    corpo = {
        "tipo": "cdb",
        "nome": "CDB X",
        "indexador": "cdi",
        "taxa": "100",
        "data_aplicacao": "2024-01-02",
        "valor_aplicado": "1000",
        "vencimento": "2024-06-07",
    }
    assert (
        api.post(f"/v1/carteiras/{cid}/investimentos", json=corpo, headers=auth()).status_code
        == 201
    )
    with db.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO proventos (ativo_id, tipo, data_com, valor, data_pagamento) "
                "SELECT ativo_id, 'jcp', '2024-06-05', 0.25, '2024-07-01' FROM ativos "
                "WHERE ticker = 'PETR4'"
            )
        )
        # Sem canal pronto, nada é gerado.
        assert gerar_avisos(db, date(2024, 6, 2)) == 0
        conn.execute(
            text(
                "INSERT INTO push_inscricoes (user_id, endpoint, p256dh, auth, criado_em) "
                "VALUES ('u1', 'https://p/1', 'k', 'a', now() - interval '1 day')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO whatsapp (user_id, telefone, confirmado_em, ativo) "
                "VALUES ('u1', '5511900000001', now() - interval '1 day', true)"
            )
        )

    # Preferências: padrão tudo ligado; desligar os vencimentos.
    url = "/v1/alertas/carteira"
    assert api.get(url, headers=auth()).json()["preferencias"]["vencimentos"] is True
    prefs = {"proventos": True, "data_com": True, "darf": True, "vencimentos": False}
    assert api.put(url, json=prefs, headers=auth()).status_code == 204

    assert gerar_avisos(db, date(2024, 6, 2)) == 2  # provento pago e data com
    assert gerar_avisos(db, date(2024, 6, 2)) == 0  # não repete
    assert api.put(url, json=prefs | {"vencimentos": True}, headers=auth()).status_code == 204
    assert gerar_avisos(db, date(2024, 6, 3)) == 1  # CDB vence em 07/06
    assert gerar_avisos(db, date(2024, 6, 24)) == 1  # DARF de maio vence em 28/06

    recentes = api.get(url, headers=auth()).json()["recentes"]
    tipos = sorted(r["tipo"] for r in recentes)
    assert tipos == ["darf", "data_com", "proventos", "vencimentos"]
    darf = next(r for r in recentes if r["tipo"] == "darf")
    assert "vence em 28/06/2024" in darf["texto"]
    assert next(r for r in recentes if r["tipo"] == "proventos")["texto"].startswith(
        "PETR4 paga R$ 1.500,00 de dividendos em 01/06/2024"
    )
    assert api.get(url, headers=auth("u2")).json()["recentes"] == []

    push, wa = PushFalso(), EvolutionFalso()
    res = enviar_avisos(db, Canais(push, wa), "https://s/")
    assert res["push"]["enviados"] == 1 and res["whatsapp"]["enviados"] == 1
    assert push.enviados == [("https://p/1", "4 avisos da carteira")]
    assert (
        "4 avisos da sua carteira" in wa.enviados[0][1]
        and "https://s/carteira" in wa.enviados[0][1]
    )
    res = enviar_avisos(db, Canais(push, wa), "https://s/")
    assert res["push"]["pendentes"] == 0 and res["whatsapp"]["pendentes"] == 0

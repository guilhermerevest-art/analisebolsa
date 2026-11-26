import json
from datetime import date

import httpx
import pytest
import respx
from sqlalchemy import text

from app.notificacao import CanalEvolution, FalhaEnvio
from app.segredo import SegredoIlegivel, cifrar, decifrar
from dominio.alertas import AVISO, Disparo, compor_codigo_whatsapp, compor_mensagem_whatsapp
from tests.test_api import cliente, token  # noqa: F401 (fixture)
from tests.test_api_carteira import api, auth  # noqa: F401
from tests.test_insights import PROIBIDAS

BASE = "https://evo.exemplo"
D = date(2026, 11, 26)


def test_segredo_cifrado_e_ilegivel_com_outra_chave():
    c = cifrar("minha-chave", "segredo-a")
    assert "minha-chave" not in c and decifrar(c, "segredo-a") == "minha-chave"
    with pytest.raises(SegredoIlegivel):
        decifrar(c, "segredo-b")


def test_mensagens_da_evolution():
    ds = [Disparo("PETR4", D, "PETR4 fechou acima de R$ 40,00."), Disparo("VALE3", D, "VALE3 x.")]
    msg = compor_mensagem_whatsapp(ds, "https://s/alertas")
    assert msg.startswith("2 alertas do pregão no analisebolsa:")
    assert "• PETR4 fechou acima de R$ 40,00.\n• VALE3 x." in msg
    assert "https://s/alertas" in msg and AVISO in msg
    assert compor_mensagem_whatsapp(ds[:1], "l").startswith("Alerta do pregão")
    assert "*123456*" in compor_codigo_whatsapp("123456")
    for t in (msg.replace(AVISO, ""), compor_codigo_whatsapp("1")):
        assert not PROIBIDAS.search(t), t


def canal(**kw):
    return CanalEvolution(BASE + "/", "minha instância", "chave-1234", httpx.Client(), 0, **kw)


def test_canal_evolution_envia_texto():
    with respx.mock() as mock:
        rota = mock.post(f"{BASE}/message/sendText/minha%20inst%C3%A2ncia").respond(201, json={})
        canal().enviar_alertas("5511987654321", [Disparo("PETR4", D, "PETR4 subiu.")], "https://l")
        canal().enviar_codigo("5511987654321", "654321")
    alerta, codigo = (json.loads(c.request.content) for c in rota.calls)
    assert rota.calls[0].request.headers["apikey"] == "chave-1234"
    assert alerta["number"] == "5511987654321" and "PETR4 subiu." in alerta["text"]
    assert "654321" in codigo["text"]

    with respx.mock() as mock:
        mock.post(f"{BASE}/message/sendText/minha%20inst%C3%A2ncia").respond(
            401, json={"response": {"message": "Unauthorized"}}
        )
        with pytest.raises(FalhaEnvio, match="401"):
            canal().enviar_codigo("5511987654321", "1")


def test_canal_evolution_numero_estado_e_qr():
    url = f"{BASE}/chat/whatsappNumbers/minha%20inst%C3%A2ncia"
    with respx.mock() as mock:
        mock.post(url).respond(200, json=[{"exists": False, "number": "5511987654321"}])
        assert canal().tem_whatsapp("5511987654321") is False
    with respx.mock() as mock:
        mock.post(url).respond(200, json=[{"exists": True, "jid": "x@s.whatsapp.net"}])
        assert canal().tem_whatsapp("5511987654321") is True
    with respx.mock() as mock:
        mock.post(url).respond(500)
        assert canal().tem_whatsapp("5511987654321") is None

    with respx.mock() as mock:
        mock.get(f"{BASE}/instance/connectionState/minha%20inst%C3%A2ncia").respond(
            200, json={"instance": {"instanceName": "minha instância", "state": "close"}}
        )
        mock.get(f"{BASE}/instance/connect/minha%20inst%C3%A2ncia").respond(
            200, json={"pairingCode": "ABCD1234", "code": "2@x", "base64": "iVBORw0KGgo="}
        )
        assert canal().estado() == "close"
        assert canal().conectar() == {
            "qr": "data:image/png;base64,iVBORw0KGgo=",
            "codigo_pareamento": "ABCD1234",
        }


def admin(sub="u1"):
    return {"Authorization": f"Bearer {token('admin', sub=sub)}"}


@pytest.fixture
def evo(api, monkeypatch):  # noqa: F811
    from app.config import get_settings

    monkeypatch.setenv("WHATSAPP_INTERVALO_S", "0")
    get_settings.cache_clear()
    with respx.mock(assert_all_called=False) as mock:
        mock.route(host="testserver").pass_through()
        yield mock
    get_settings.cache_clear()


CORPO = {"url": BASE + "/", "instancia": "principal", "chave": "chave-secreta-9876"}


@pytest.mark.db
def test_admin_cadastra_a_instancia_sem_expor_a_chave(api, evo, db):  # noqa: F811
    url = "/v1/admin/whatsapp"
    assert api.get(url, headers=auth()).status_code == 403
    vazio = api.get(url, headers=admin()).json()
    assert vazio["configurada"] is False and vazio["provedor_em_uso"] is None

    assert api.put(url, json=CORPO | {"chave": None}, headers=admin()).status_code == 422
    assert api.put(url, json=CORPO | {"url": "ftp://x"}, headers=admin()).status_code == 422
    r = api.put(url, json=CORPO, headers=admin())
    assert r.status_code == 200, r.text
    dados = r.json()
    assert dados["url"] == BASE and dados["chave_final"] == "…9876"
    assert dados["provedor_em_uso"] == "evolution" and "chave-secreta" not in r.text
    with db.connect() as conn:
        guardada = conn.execute(text("SELECT chave_cifrada FROM config_whatsapp")).scalar()
    assert "chave-secreta" not in guardada

    # Sem chave nova, mantém a guardada; desligada, não é usada para os alertas.
    r = api.put(url, json=CORPO | {"chave": "", "ativo": False}, headers=admin())
    assert r.json()["chave_final"] == "…9876" and r.json()["provedor_em_uso"] is None
    assert api.delete(url, headers=admin()).status_code == 204
    assert api.get(url, headers=admin()).json()["configurada"] is False


@pytest.mark.db
def test_admin_estado_qr_e_teste(api, evo):  # noqa: F811
    assert api.get("/v1/admin/whatsapp/estado", headers=admin()).status_code == 404
    api.put("/v1/admin/whatsapp", json=CORPO, headers=admin())

    evo.get(f"{BASE}/instance/connectionState/principal").respond(
        200, json={"instance": {"state": "connecting"}}
    )
    evo.get(f"{BASE}/instance/connect/principal").respond(
        200, json={"base64": "data:image/png;base64,AAA", "pairingCode": None}
    )
    r = api.get("/v1/admin/whatsapp/estado", headers=admin()).json()
    assert r == {
        "estado": "connecting",
        "qr": "data:image/png;base64,AAA",
        "codigo_pareamento": None,
        "erro": None,
    }

    envio = evo.post(f"{BASE}/message/sendText/principal").respond(201, json={})
    r = api.post("/v1/admin/whatsapp/teste", json={"numero": "11987654321"}, headers=admin())
    assert r.status_code == 204
    assert json.loads(envio.calls[-1].request.content)["number"] == "5511987654321"
    assert envio.calls[-1].request.headers["apikey"] == "chave-secreta-9876"


@pytest.mark.db
def test_admin_estado_com_evolution_fora(api, evo):  # noqa: F811
    api.put("/v1/admin/whatsapp", json=CORPO, headers=admin())
    evo.get(f"{BASE}/instance/connectionState/principal").respond(401, text="Unauthorized")
    r = api.get("/v1/admin/whatsapp/estado", headers=admin()).json()
    assert r["estado"] == "erro" and "401" in r["erro"]


@pytest.mark.db
def test_usuario_confirma_numero_pela_instancia(api, evo, db):  # noqa: F811
    api.put("/v1/admin/whatsapp", json=CORPO, headers=admin())
    evo.post(f"{BASE}/chat/whatsappNumbers/principal").respond(200, json=[{"exists": True}])
    envio = evo.post(f"{BASE}/message/sendText/principal").respond(201, json={})

    estado = api.get("/v1/notificacoes", headers=auth("u2")).json()["whatsapp"]
    assert estado["disponivel"] is True
    r = api.put("/v1/notificacoes/whatsapp", json={"numero": "11987654321"}, headers=auth("u2"))
    assert r.status_code == 200, r.text
    texto = json.loads(envio.calls[-1].request.content)["text"]
    codigo = texto.split("*")[1]
    r = api.post("/v1/notificacoes/whatsapp/confirmar", json={"codigo": codigo}, headers=auth("u2"))
    assert r.json()["whatsapp"]["confirmado"] is True

    # O worker também usa a instância.
    from app.config import get_settings
    from worker.alertas import canais_do_worker

    assert isinstance(canais_do_worker(db, get_settings()).whatsapp, CanalEvolution)

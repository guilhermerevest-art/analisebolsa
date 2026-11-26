import re
from datetime import date

import pytest
from sqlalchemy import text

from app.rotas.notificacoes import canal_push, canal_whatsapp
from dominio.alertas import Disparo
from dominio.telefone import mascarar_telefone, normalizar_telefone
from tests.test_alertas import PushFalso, WhatsAppFalso
from tests.test_api import cliente, token  # noqa: F401 (fixture)
from tests.test_api_carteira import api, auth  # noqa: F401


@pytest.mark.parametrize(
    ("entrada", "saida"),
    [
        ("(11) 98765-4321", "5511987654321"),
        ("11 98765 4321", "5511987654321"),
        ("+55 11 98765-4321", "5511987654321"),
        ("011987654321", "5511987654321"),
        ("(21) 3456-7890", "552134567890"),
        ("+351 912 345 678", "351912345678"),
        ("0055 11 98765-4321", "5511987654321"),
        ("12345", None),
        ("(11) 18765-4321", None),  # celular sem o 9
        ("(10) 98765-4321", None),  # DDD inválido
        ("98765-4321", None),  # sem DDD
        ("5511987654321", "5511987654321"),
        ("abc", None),
    ],
)
def test_normalizar_telefone(entrada, saida):
    assert normalizar_telefone(entrada) == saida


def test_mascarar_telefone():
    assert mascarar_telefone("5511987654321") == "+55 (11) 9****-4321"
    assert mascarar_telefone("351912345678") == "+35 ****5678"


@pytest.fixture
def canais(api, monkeypatch):  # noqa: F811
    from app.config import get_settings

    monkeypatch.setenv("VAPID_PUBLIC_KEY", "chave-publica")
    get_settings.cache_clear()
    push, wa = PushFalso(expirados={"https://push.exemplo/velho"}), WhatsAppFalso()
    app = api.app
    app.dependency_overrides[canal_push] = lambda: push
    app.dependency_overrides[canal_whatsapp] = lambda: wa
    yield push, wa
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def inscricao(endpoint="https://push.exemplo/1", **extra):
    return {"endpoint": endpoint, "keys": {"p256dh": "p" * 40, "auth": "a" * 16}} | extra


@pytest.mark.db
def test_estado_sem_canais_configurados(api):  # noqa: F811
    assert api.get("/v1/notificacoes").status_code == 401
    r = api.get("/v1/notificacoes", headers=auth())
    assert r.status_code == 200 and r.headers["cache-control"] == "private, no-store"
    assert r.json() == {
        "push": {"disponivel": False, "chave_publica": None, "aparelhos": []},
        "whatsapp": {"disponivel": False, "telefone": None, "confirmado": False, "ativo": False},
    }
    assert api.post("/v1/notificacoes/push", json=inscricao(), headers=auth()).status_code == 503
    r = api.put("/v1/notificacoes/whatsapp", json={"numero": "11987654321"}, headers=auth())
    assert r.status_code == 503


@pytest.mark.db
def test_push_registrar_testar_remover_e_isolamento(api, canais):  # noqa: F811
    push, _ = canais
    for corpo in (inscricao(aparelho="Chrome no Android"), inscricao()):  # idempotente
        assert api.post("/v1/notificacoes/push", json=corpo, headers=auth()).status_code == 204
    velho = inscricao("https://push.exemplo/velho")
    assert api.post("/v1/notificacoes/push", json=velho, headers=auth()).status_code == 204
    r = api.post("/v1/notificacoes/push", json=inscricao("http://inseguro"), headers=auth())
    assert r.status_code == 422

    estado = api.get("/v1/notificacoes", headers=auth()).json()["push"]
    assert estado["disponivel"] and estado["chave_publica"] == "chave-publica"
    assert len(estado["aparelhos"]) == 2
    assert api.get("/v1/notificacoes", headers=auth("u2")).json()["push"]["aparelhos"] == []

    r = api.post("/v1/notificacoes/push/teste", headers=auth())
    assert r.json() == {"enviados": 1}  # o expirado sai
    assert push.enviados == [("https://push.exemplo/1", "Notificações ligadas")]
    (aparelho,) = api.get("/v1/notificacoes", headers=auth()).json()["push"]["aparelhos"]

    cancelar = {"endpoint": "https://push.exemplo/1"}
    assert (
        api.post("/v1/notificacoes/push/cancelar", json=cancelar, headers=auth("u2")).status_code
        == 204
    )
    assert len(api.get("/v1/notificacoes", headers=auth()).json()["push"]["aparelhos"]) == 1
    assert (
        api.post("/v1/notificacoes/push/cancelar", json=cancelar, headers=auth()).status_code == 204
    )
    assert api.get("/v1/notificacoes", headers=auth()).json()["push"]["aparelhos"] == []
    api.post("/v1/notificacoes/push", json=inscricao(), headers=auth())
    (aparelho,) = api.get("/v1/notificacoes", headers=auth()).json()["push"]["aparelhos"]

    caminho = f"/v1/notificacoes/push/{aparelho['id']}"
    assert api.delete(caminho, headers=auth("u2")).status_code == 404
    assert api.delete(caminho, headers=auth()).status_code == 204
    assert api.delete(caminho, headers=auth()).status_code == 404


@pytest.mark.db
def test_push_limite_de_aparelhos(api, canais, monkeypatch):  # noqa: F811
    from app import notificacoes

    monkeypatch.setattr(notificacoes, "LIMITE_APARELHOS", 1)
    assert api.post("/v1/notificacoes/push", json=inscricao(), headers=auth()).status_code == 204
    r = api.post("/v1/notificacoes/push", json=inscricao("https://push.exemplo/2"), headers=auth())
    assert r.status_code == 409


@pytest.mark.db
def test_whatsapp_codigo_confirmacao_pausa_e_remocao(api, canais, db):  # noqa: F811
    _, wa = canais
    url = "/v1/notificacoes/whatsapp"
    assert api.put(url, json={"numero": "123456789"}, headers=auth()).status_code == 422
    r = api.put(url, json={"numero": "(11) 98765-4321"}, headers=auth())
    assert r.status_code == 200, r.text
    assert r.json()["whatsapp"] == {
        "disponivel": True,
        "telefone": "+55 (11) 9****-4321",
        "confirmado": False,
        "ativo": True,
    }
    telefone, codigo = wa.enviados[-1]
    assert telefone == "5511987654321" and re.fullmatch(r"\d{6}", codigo)
    with db.connect() as conn:
        guardado = conn.execute(text("SELECT codigo_hash FROM whatsapp")).scalar()
    assert codigo not in guardado

    errado = "000000" if codigo != "000000" else "111111"
    r = api.post(f"{url}/confirmar", json={"codigo": errado}, headers=auth())
    assert r.status_code == 422 and r.json()["detail"] == "código incorreto"
    assert (
        api.post(f"{url}/confirmar", json={"codigo": codigo}, headers=auth("u2")).status_code == 404
    )
    r = api.post(f"{url}/confirmar", json={"codigo": codigo}, headers=auth())
    assert r.json()["whatsapp"]["confirmado"] is True

    # Mesmo número já confirmado: não manda outro código.
    n = len(wa.enviados)
    api.put(url, json={"numero": "+55 11 98765-4321"}, headers=auth())
    assert len(wa.enviados) == n

    assert (
        api.patch(url, json={"ativo": False}, headers=auth()).json()["whatsapp"]["ativo"] is False
    )
    assert api.patch(url, json={"ativo": True}, headers=auth("u2")).status_code == 404

    # Trocar de número volta a exigir confirmação.
    r = api.put(url, json={"numero": "21 98765-0000"}, headers=auth())
    assert r.json()["whatsapp"]["confirmado"] is False

    assert api.delete(url, headers=auth()).status_code == 204
    estado = api.get("/v1/notificacoes", headers=auth()).json()["whatsapp"]
    assert estado["telefone"] is None


@pytest.mark.db
def test_whatsapp_codigo_expirado_tentativas_e_limite_diario(api, canais, db):  # noqa: F811
    _, wa = canais
    url = "/v1/notificacoes/whatsapp"
    api.put(url, json={"numero": "11987654321"}, headers=auth())
    codigo = wa.enviados[-1][1]
    errado = "000000" if codigo != "000000" else "111111"
    for _ in range(5):
        api.post(f"{url}/confirmar", json={"codigo": errado}, headers=auth())
    r = api.post(f"{url}/confirmar", json={"codigo": codigo}, headers=auth())
    assert r.status_code == 429

    api.put(url, json={"numero": "11987654321"}, headers=auth())  # novo código zera
    with db.begin() as conn:
        conn.execute(text("UPDATE whatsapp SET codigo_expira_em = now() - interval '1 minute'"))
    r = api.post(f"{url}/confirmar", json={"codigo": wa.enviados[-1][1]}, headers=auth())
    assert r.status_code == 422 and "expirado" in r.json()["detail"]

    for _ in range(3):
        assert api.put(url, json={"numero": "11987654321"}, headers=auth()).status_code == 200
    assert api.put(url, json={"numero": "11987654321"}, headers=auth()).status_code == 429


@pytest.mark.db
def test_whatsapp_falha_no_envio_do_codigo(api, canais):  # noqa: F811
    _, wa = canais

    def falhar(telefone, codigo):
        raise OSError("meta fora")

    wa.enviar_codigo = falhar
    r = api.put("/v1/notificacoes/whatsapp", json={"numero": "11987654321"}, headers=auth())
    assert r.status_code == 502
    assert api.get("/v1/notificacoes", headers=auth()).json()["whatsapp"]["telefone"] is None


def test_canal_whatsapp_monta_os_modelos():
    import httpx
    import respx

    from app.config import Settings
    from app.notificacao import CanalWhatsApp, FalhaEnvio

    s = Settings(whatsapp_token="tok", whatsapp_phone_number_id="123")
    with respx.mock() as mock:
        rota = mock.post("https://graph.facebook.com/v23.0/123/messages").respond(200, json={})
        canal = CanalWhatsApp(s, httpx.Client())
        canal.enviar_alertas(
            "5511987654321",
            [Disparo("PETR4", date(2026, 11, 26), "PETR4 subiu.")],
            "https://s/alertas",
        )
        canal.enviar_codigo("5511987654321", "123456")
        alerta, codigo = (__import__("json").loads(c.request.content) for c in rota.calls)
        assert rota.calls[0].request.headers["authorization"] == "Bearer tok"
    assert alerta["to"] == "5511987654321" and alerta["type"] == "template"
    assert alerta["template"]["name"] == "alertas_disparados"
    assert alerta["template"]["language"] == {"code": "pt_BR"}
    assert [p["text"] for p in alerta["template"]["components"][0]["parameters"]] == [
        "PETR4 subiu",
        "https://s/alertas",
    ]
    assert codigo["template"]["name"] == "codigo_verificacao"
    botao = codigo["template"]["components"][1]
    assert botao["sub_type"] == "url" and botao["parameters"][0]["text"] == "123456"

    with respx.mock() as mock:
        mock.post("https://graph.facebook.com/v23.0/123/messages").respond(
            400, json={"error": {"code": 132001, "message": "Template name does not exist"}}
        )
        with pytest.raises(FalhaEnvio, match="132001"):
            CanalWhatsApp(s, httpx.Client()).enviar_codigo("5511987654321", "1")


def test_canal_push_criptografa_assina_e_detecta_expirada(monkeypatch):
    import base64

    import requests
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    from app.notificacao import CanalPush, FalhaEnvio, InscricaoExpirada, gerar_vapid

    # Chaves do "navegador" que assina a inscrição.
    nav = ec.generate_private_key(ec.SECP256R1())
    p256dh = base64.urlsafe_b64encode(
        nav.public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
    ).decode()
    auth = base64.urlsafe_b64encode(b"0123456789abcdef").decode()
    publica, privada = gerar_vapid()
    assert len(base64.urlsafe_b64decode(publica + "==")) == 65

    chamadas, status = [], {"v": 201}

    class Resp:
        def __init__(self, code):
            self.status_code, self.text, self.content, self.headers = code, "", b"", {}
            self.reason = ""

    def post(url, data=None, headers=None, timeout=None, **kw):
        chamadas.append((url, headers, data))
        return Resp(status["v"])

    monkeypatch.setattr(requests, "post", post)
    canal = CanalPush(privada, "mailto:a@b.c")
    canal.enviar("https://push.exemplo/x", p256dh, auth, {"titulo": "t", "corpo": "c"})
    url, headers, data = chamadas[0]
    assert url == "https://push.exemplo/x" and headers["content-encoding"] == "aes128gcm"
    assert headers["authorization"].startswith("vapid t=") and publica in headers["authorization"]
    assert b"titulo" not in data  # cifrado

    status["v"] = 410
    with pytest.raises(InscricaoExpirada):
        canal.enviar("https://push.exemplo/x", p256dh, auth, {})
    status["v"] = 500
    with pytest.raises(FalhaEnvio):
        canal.enviar("https://push.exemplo/x", p256dh, auth, {})


@pytest.mark.db
def test_whatsapp_numero_sem_whatsapp(api, canais):  # noqa: F811
    r = api.put("/v1/notificacoes/whatsapp", json={"numero": "11 99999-9999"}, headers=auth())
    assert r.status_code == 422 and r.json()["detail"] == "esse número não tem WhatsApp"

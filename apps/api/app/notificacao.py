"""Canais de notificação dos alertas: push (Web Push) e WhatsApp (Evolution API ou Meta).

A API usa os canais para o push de teste e o código do WhatsApp; o worker, para os alertas.
Canal sem configuração não é criado (`push_configurado` e `whatsapp_configurado` devolvem None).

`python -m app.notificacao vapid` gera um par de chaves VAPID.
"""

import base64
import json
import logging
import sys
import time
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import quote

import httpx

from app.config import Settings
from dominio.alertas import (
    Disparo,
    compor_codigo_whatsapp,
    compor_mensagem_whatsapp,
    compor_whatsapp,
)

log = logging.getLogger("notificacao")


class InscricaoExpirada(Exception):
    """O serviço de push diz que a inscrição não existe mais (404 ou 410): apagar."""


class FalhaEnvio(Exception):
    pass


class EnviadorPush(Protocol):
    def enviar(self, endpoint: str, p256dh: str, auth: str, payload: dict) -> None: ...


class EnviadorWhatsApp(Protocol):
    def enviar_alertas(self, telefone: str, disparos: list[Disparo], link: str) -> None: ...
    def enviar_codigo(self, telefone: str, codigo: str) -> None: ...
    def tem_whatsapp(self, telefone: str) -> bool | None:
        """True/False se o canal sabe dizer se o número usa WhatsApp; None se não sabe."""
        ...


class CanalPush:
    def __init__(self, chave_privada: str, contato: str):
        self.chave_privada, self.contato = chave_privada, contato

    def enviar(self, endpoint: str, p256dh: str, auth: str, payload: dict) -> None:
        from pywebpush import WebPushException, webpush

        try:
            webpush(
                {"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth}},
                json.dumps(payload, ensure_ascii=False),
                vapid_private_key=self.chave_privada,
                vapid_claims={"sub": self.contato},
                ttl=24 * 3600,
                timeout=20,
            )
        except WebPushException as e:
            status = getattr(e.response, "status_code", None)
            if status in (404, 410):
                raise InscricaoExpirada from e
            raise FalhaEnvio(f"push {status}") from e


class CanalWhatsApp:
    def __init__(self, settings: Settings, cliente: httpx.Client | None = None):
        self.s = settings
        self.url = (
            f"{settings.whatsapp_api_url.rstrip('/')}/{settings.whatsapp_api_versao}/"
            f"{settings.whatsapp_phone_number_id}/messages"
        )
        self.cliente = cliente or httpx.Client(timeout=20)

    def _modelo(self, telefone: str, nome: str, componentes: list[dict]) -> None:
        corpo = {
            "messaging_product": "whatsapp",
            "to": telefone,
            "type": "template",
            "template": {
                "name": nome,
                "language": {"code": self.s.whatsapp_idioma},
                "components": componentes,
            },
        }
        r = self.cliente.post(
            self.url, json=corpo, headers={"Authorization": f"Bearer {self.s.whatsapp_token}"}
        )
        if r.status_code >= 400:
            # A mensagem de erro da Meta não traz o token; o telefone fica fora do log.
            erro = (
                r.json().get("error", {})
                if r.headers.get("content-type", "").startswith("application/json")
                else {}
            )
            raise FalhaEnvio(f"whatsapp {r.status_code} {erro.get('code')} {erro.get('message')}")

    def tem_whatsapp(self, telefone: str) -> bool | None:
        return None

    def enviar_alertas(self, telefone: str, disparos: list[Disparo], link: str) -> None:
        textos = compor_whatsapp(disparos)
        self._modelo(
            telefone,
            self.s.whatsapp_modelo_alertas,
            [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": textos},
                        {"type": "text", "text": link},
                    ],
                }
            ],
        )

    def enviar_codigo(self, telefone: str, codigo: str) -> None:
        # Modelo de autenticação: o código vai no corpo e no botão de copiar.
        self._modelo(
            telefone,
            self.s.whatsapp_modelo_codigo,
            [
                {"type": "body", "parameters": [{"type": "text", "text": codigo}]},
                {
                    "type": "button",
                    "sub_type": "url",
                    "index": "0",
                    "parameters": [{"type": "text", "text": codigo}],
                },
            ],
        )


class CanalEvolution:
    """WhatsApp pela Evolution API (v2), numa instância própria conectada por QR code.

    Usa o protocolo do WhatsApp Web: mensagens livres, sem modelo aprovado. Para reduzir o
    risco de bloqueio do número, há uma pausa entre envios.
    """

    def __init__(
        self,
        url: str,
        instancia: str,
        chave: str,
        cliente: httpx.Client | None = None,
        intervalo_s: float = 2.0,
    ):
        self.base = url.rstrip("/")
        self.instancia = quote(instancia, safe="")
        self.cabecalhos = {"apikey": chave}
        self.cliente = cliente or httpx.Client(timeout=20)
        self.intervalo_s = intervalo_s

    def _url(self, caminho: str) -> str:
        return f"{self.base}/{caminho}/{self.instancia}"

    def _checar(self, r: httpx.Response, o_que: str) -> dict | list:
        if r.status_code >= 400:
            detalhe = r.text[:200].replace("\n", " ")
            raise FalhaEnvio(f"evolution {o_que} {r.status_code} {detalhe}")
        try:
            return r.json()
        except ValueError:
            return {}

    def enviar_texto(self, telefone: str, texto: str) -> None:
        r = self.cliente.post(
            self._url("message/sendText"),
            json={"number": telefone, "text": texto},
            headers=self.cabecalhos,
        )
        self._checar(r, "sendText")
        if self.intervalo_s:
            time.sleep(self.intervalo_s)

    def enviar_alertas(self, telefone: str, disparos: list[Disparo], link: str) -> None:
        self.enviar_texto(telefone, compor_mensagem_whatsapp(disparos, link))

    def enviar_codigo(self, telefone: str, codigo: str) -> None:
        self.enviar_texto(telefone, compor_codigo_whatsapp(codigo))

    def tem_whatsapp(self, telefone: str) -> bool | None:
        try:
            r = self.cliente.post(
                self._url("chat/whatsappNumbers"),
                json={"numbers": [telefone]},
                headers=self.cabecalhos,
            )
            dados = self._checar(r, "whatsappNumbers")
        except (FalhaEnvio, httpx.HTTPError):
            return None  # na dúvida, deixa o envio do código decidir
        if isinstance(dados, list) and dados:
            return bool(dados[0].get("exists"))
        return None

    def estado(self) -> str:
        """ "open" (conectada), "connecting", "close" ou o que a Evolution responder."""
        r = self.cliente.get(self._url("instance/connectionState"), headers=self.cabecalhos)
        dados = self._checar(r, "connectionState")
        return str(
            (dados.get("instance") or {}).get("state") or dados.get("state") or "desconhecido"
        )

    def conectar(self) -> dict:
        """QR code (data URL) e código de pareamento para conectar a instância."""
        r = self.cliente.get(self._url("instance/connect"), headers=self.cabecalhos)
        dados = self._checar(r, "connect")
        qr = dados.get("base64")
        if qr and not str(qr).startswith("data:image"):
            qr = f"data:image/png;base64,{qr}"
        return {"qr": qr, "codigo_pareamento": dados.get("pairingCode")}


def push_configurado(settings: Settings) -> CanalPush | None:
    if not settings.vapid_public_key or not settings.vapid_private_key:
        return None
    contato = settings.vapid_contato or settings.url_publica or "mailto:contato@analisebolsa.app"
    return CanalPush(settings.vapid_private_key, contato)


def whatsapp_configurado(settings: Settings) -> CanalWhatsApp | None:
    if not settings.whatsapp_token or not settings.whatsapp_phone_number_id:
        return None
    return CanalWhatsApp(settings)


@dataclass(frozen=True, slots=True)
class Canais:
    push: EnviadorPush | None = None
    whatsapp: EnviadorWhatsApp | None = None


def canais_configurados(settings: Settings, whatsapp: EnviadorWhatsApp | None = None) -> Canais:
    """Push pelo ambiente; o WhatsApp vem de `app.whatsapp_config.canal_whatsapp` (banco)."""
    return Canais(push_configurado(settings), whatsapp)


def gerar_vapid() -> tuple[str, str]:
    """Par (pública, privada) em base64url: o formato que o navegador e o pywebpush aceitam."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    chave = ec.generate_private_key(ec.SECP256R1())
    b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()  # noqa: E731
    publica = chave.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return b64(publica), b64(chave.private_numbers().private_value.to_bytes(32, "big"))


if __name__ == "__main__":
    if sys.argv[1:] != ["vapid"]:
        sys.exit("uso: python -m app.notificacao vapid")
    pub, priv = gerar_vapid()
    print(f"VAPID_PUBLIC_KEY={pub}\nVAPID_PRIVATE_KEY={priv}")

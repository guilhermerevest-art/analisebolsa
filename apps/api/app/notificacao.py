"""Canais de notificação dos alertas: push (Web Push) e WhatsApp (Cloud API da Meta).

A API usa os canais para o push de teste e o código do WhatsApp; o worker, para os alertas.
Canal sem configuração não é criado (`push_configurado` e `whatsapp_configurado` devolvem None).

`python -m app.notificacao vapid` gera um par de chaves VAPID.
"""

import base64
import json
import logging
import sys
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.config import Settings

log = logging.getLogger("notificacao")


class InscricaoExpirada(Exception):
    """O serviço de push diz que a inscrição não existe mais (404 ou 410): apagar."""


class FalhaEnvio(Exception):
    pass


class EnviadorPush(Protocol):
    def enviar(self, endpoint: str, p256dh: str, auth: str, payload: dict) -> None: ...


class EnviadorWhatsApp(Protocol):
    def enviar_alertas(self, telefone: str, textos: str, link: str) -> None: ...
    def enviar_codigo(self, telefone: str, codigo: str) -> None: ...


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
            f"https://graph.facebook.com/{settings.whatsapp_api_versao}/"
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

    def enviar_alertas(self, telefone: str, textos: str, link: str) -> None:
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


def canais_configurados(settings: Settings) -> Canais:
    return Canais(push_configurado(settings), whatsapp_configurado(settings))


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

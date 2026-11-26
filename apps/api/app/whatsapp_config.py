"""Instância do WhatsApp cadastrada no /admin (Evolution API) e escolha do canal.

Ordem: a instância da Evolution ligada no /admin; senão a Cloud API da Meta, se houver as
variáveis de ambiente; senão nenhum (os alertas esperam).
"""

import logging
import re

from sqlalchemy import Connection, text

from app.config import Settings
from app.erros import Problema
from app.notificacao import CanalEvolution, EnviadorWhatsApp, whatsapp_configurado
from app.segredo import SegredoIlegivel, cifrar, decifrar

log = logging.getLogger("whatsapp")


def _linha(conn: Connection):
    return (
        conn.execute(
            text("SELECT url, instancia, chave_cifrada, ativo, atualizado_em FROM config_whatsapp")
        )
        .mappings()
        .one_or_none()
    )


def evolution(conn: Connection, settings: Settings) -> CanalEvolution | None:
    """Canal da instância cadastrada, mesmo desligada (para o /admin testar)."""
    r = _linha(conn)
    if r is None:
        return None
    try:
        chave = decifrar(r["chave_cifrada"], settings.internal_jwt_secret)
    except SegredoIlegivel:
        log.warning("whatsapp: chave da instância ilegível; cadastre de novo no /admin")
        return None
    return CanalEvolution(
        r["url"], r["instancia"], chave, intervalo_s=settings.whatsapp_intervalo_s
    )


def canal_whatsapp(conn: Connection, settings: Settings) -> EnviadorWhatsApp | None:
    r = _linha(conn)
    if r is not None and r["ativo"]:
        canal = evolution(conn, settings)
        if canal is not None:
            return canal
    return whatsapp_configurado(settings)


def provedor(conn: Connection, settings: Settings) -> str | None:
    r = _linha(conn)
    if r is not None and r["ativo"]:
        return "evolution"
    return "meta" if whatsapp_configurado(settings) else None


def ler(conn: Connection, settings: Settings) -> dict:
    r = _linha(conn)
    base = {"provedor_em_uso": provedor(conn, settings)}
    if r is None:
        return base | {
            "configurada": False,
            "url": None,
            "instancia": None,
            "chave_final": None,
            "ativo": False,
            "atualizado_em": None,
        }
    try:
        final = "…" + decifrar(r["chave_cifrada"], settings.internal_jwt_secret)[-4:]
    except SegredoIlegivel:
        final = None
    return base | {
        "configurada": True,
        "url": r["url"],
        "instancia": r["instancia"],
        "chave_final": final,
        "ativo": r["ativo"],
        "atualizado_em": r["atualizado_em"],
    }


def salvar(
    conn: Connection,
    settings: Settings,
    admin_id: str,
    url: str,
    instancia: str,
    chave: str | None,
    ativo: bool,
) -> None:
    url = url.strip().rstrip("/")
    if not re.fullmatch(r"https?://[^\s/$.?#][^\s]*", url):
        raise Problema(422, "informe a URL da Evolution API, ex.: https://evolution.seudominio.com")
    instancia = instancia.strip()
    atual = _linha(conn)
    if chave:
        cifrada = cifrar(chave.strip(), settings.internal_jwt_secret)
    elif atual is not None:
        cifrada = atual["chave_cifrada"]
    else:
        raise Problema(422, "informe a API key da instância")
    conn.execute(
        text(
            """
            INSERT INTO config_whatsapp (id, url, instancia, chave_cifrada, ativo, atualizado_por)
            VALUES (true, :url, :i, :c, :a, :u)
            ON CONFLICT (id) DO UPDATE SET url = :url, instancia = :i, chave_cifrada = :c,
              ativo = :a, atualizado_em = now(), atualizado_por = :u
            """
        ),
        {"url": url, "i": instancia, "c": cifrada, "a": ativo, "u": admin_id},
    )


def remover(conn: Connection) -> None:
    conn.execute(text("DELETE FROM config_whatsapp"))

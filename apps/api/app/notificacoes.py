"""Canais de notificação do usuário (Fase 5, etapa 1). Toda consulta filtra pelo usuário."""

import hashlib
import hmac
import logging
import secrets
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Connection, Engine, text

from app.erros import Problema
from app.notificacao import EnviadorPush, EnviadorWhatsApp, InscricaoExpirada
from app.usuario import exigir_usuario_existente
from dominio.telefone import mascarar_telefone, normalizar_telefone

LIMITE_APARELHOS = 10
VALIDADE_CODIGO = timedelta(minutes=10)
TENTATIVAS_CODIGO = 5
CODIGOS_POR_DIA = 5
FUSO = ZoneInfo("America/Sao_Paulo")
log = logging.getLogger("notificacoes")


def estado(
    conn: Connection, user_id: str, chave_publica: str | None, whatsapp_disponivel: bool
) -> dict:
    aparelhos = [
        dict(r)
        for r in conn.execute(
            text(
                "SELECT inscricao_id AS id, aparelho, criado_em FROM push_inscricoes "
                "WHERE user_id = :u ORDER BY criado_em"
            ),
            {"u": user_id},
        ).mappings()
    ]
    wa = (
        conn.execute(
            text("SELECT telefone, confirmado_em, ativo FROM whatsapp WHERE user_id = :u"),
            {"u": user_id},
        )
        .mappings()
        .one_or_none()
    )
    return {
        "push": {
            "disponivel": chave_publica is not None,
            "chave_publica": chave_publica,
            "aparelhos": aparelhos,
        },
        "whatsapp": {
            "disponivel": whatsapp_disponivel,
            "telefone": mascarar_telefone(wa["telefone"]) if wa else None,
            "confirmado": bool(wa and wa["confirmado_em"]),
            "ativo": bool(wa and wa["ativo"]),
        },
    }


# Push


def registrar_push(
    conn: Connection, user_id: str, endpoint: str, p256dh: str, auth: str, aparelho: str | None
) -> None:
    """Idempotente pelo endpoint; se o aparelho mudou de conta, passa para a conta atual."""
    exigir_usuario_existente(conn, user_id)
    existe = conn.execute(
        text("SELECT user_id FROM push_inscricoes WHERE endpoint = :e"), {"e": endpoint}
    ).scalar()
    if existe != user_id:
        n = conn.execute(
            text("SELECT count(*) FROM push_inscricoes WHERE user_id = :u"), {"u": user_id}
        ).scalar_one()
        if n >= LIMITE_APARELHOS:
            raise Problema(409, f"cada conta pode ter até {LIMITE_APARELHOS} aparelhos com push")
    conn.execute(
        text(
            """
            INSERT INTO push_inscricoes (user_id, endpoint, p256dh, auth, aparelho)
            VALUES (:u, :e, :p, :a, :ap)
            ON CONFLICT (endpoint) DO UPDATE SET user_id = :u, p256dh = :p, auth = :a,
              aparelho = :ap,
              criado_em = CASE WHEN push_inscricoes.user_id = :u
                               THEN push_inscricoes.criado_em ELSE now() END
            """
        ),
        {"u": user_id, "e": endpoint, "p": p256dh, "a": auth, "ap": aparelho},
    )


def cancelar_push(conn: Connection, user_id: str, endpoint: str) -> None:
    """Remove pelo endpoint (o navegador conhece o próprio endpoint, não o id)."""
    conn.execute(
        text("DELETE FROM push_inscricoes WHERE endpoint = :e AND user_id = :u"),
        {"e": endpoint, "u": user_id},
    )


def remover_push(conn: Connection, user_id: str, inscricao_id: int) -> None:
    apagado = conn.execute(
        text("DELETE FROM push_inscricoes WHERE inscricao_id = :i AND user_id = :u"),
        {"i": inscricao_id, "u": user_id},
    ).rowcount
    if not apagado:
        raise Problema(404, "aparelho não encontrado")


def enviar_push_para(engine: Engine, push: EnviadorPush, user_id: str, payload: dict) -> int:
    """Envia para todos os aparelhos do usuário. Apaga os expirados; devolve quantos receberam."""
    with engine.connect() as conn:
        inscricoes = (
            conn.execute(
                text(
                    "SELECT inscricao_id, endpoint, p256dh, auth FROM push_inscricoes "
                    "WHERE user_id = :u ORDER BY inscricao_id"
                ),
                {"u": user_id},
            )
            .mappings()
            .all()
        )
    entregues = 0
    for i in inscricoes:
        try:
            push.enviar(i["endpoint"], i["p256dh"], i["auth"], payload)
            entregues += 1
        except InscricaoExpirada:
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM push_inscricoes WHERE inscricao_id = :i"),
                    {"i": i["inscricao_id"]},
                )
        except Exception:  # um aparelho com problema não impede os outros
            log.exception("push: falha num aparelho")
    return entregues


def testar_push(conn: Connection, user_id: str, push: EnviadorPush) -> int:
    payload = {
        "titulo": "Notificações ligadas",
        "corpo": "Os alertas do analisebolsa vão chegar neste aparelho.",
        "url": "/alertas",
    }
    return enviar_push_para(conn.engine, push, user_id, payload)


# WhatsApp


def _hash(user_id: str, codigo: str, segredo: str) -> str:
    return hmac.new(segredo.encode(), f"{user_id}:{codigo}".encode(), hashlib.sha256).hexdigest()


def cadastrar_whatsapp(
    conn: Connection, user_id: str, numero: str, wa: EnviadorWhatsApp, segredo: str
) -> None:
    """Cadastra ou troca o número e envia o código de confirmação pelo WhatsApp."""
    exigir_usuario_existente(conn, user_id)
    telefone = normalizar_telefone(numero)
    if telefone is None:
        raise Problema(422, "número inválido: informe o DDD e o número, ex.: (11) 98765-4321")
    atual = (
        conn.execute(
            text(
                "SELECT telefone, confirmado_em, codigos_dia, codigos_data FROM whatsapp "
                "WHERE user_id = :u"
            ),
            {"u": user_id},
        )
        .mappings()
        .one_or_none()
    )
    if atual and atual["telefone"] == telefone and atual["confirmado_em"]:
        return  # já confirmado: nada a enviar
    hoje = datetime.now(FUSO).date()
    usados = atual["codigos_dia"] if atual and atual["codigos_data"] == hoje else 0
    if usados >= CODIGOS_POR_DIA:
        raise Problema(429, "limite de códigos por hoje atingido; tente amanhã")

    codigo = f"{secrets.randbelow(10**6):06d}"
    try:
        wa.enviar_codigo(telefone, codigo)
    except Exception as e:
        raise Problema(502, "não foi possível enviar o código pelo WhatsApp agora") from e
    conn.execute(
        text(
            """
            INSERT INTO whatsapp (user_id, telefone, codigo_hash, codigo_expira_em, tentativas,
                                  codigos_dia, codigos_data)
            VALUES (:u, :t, :h, :x, 0, :n, :d)
            ON CONFLICT (user_id) DO UPDATE SET telefone = :t, confirmado_em = NULL,
              codigo_hash = :h, codigo_expira_em = :x, tentativas = 0, codigos_dia = :n,
              codigos_data = :d
            """
        ),
        {
            "u": user_id,
            "t": telefone,
            "h": _hash(user_id, codigo, segredo),
            "x": datetime.now(UTC) + VALIDADE_CODIGO,
            "n": usados + 1,
            "d": hoje,
        },
    )


def confirmar_whatsapp(conn: Connection, user_id: str, codigo: str, segredo: str) -> None:
    r = (
        conn.execute(
            text(
                "SELECT codigo_hash, codigo_expira_em, tentativas, confirmado_em FROM whatsapp "
                "WHERE user_id = :u"
            ),
            {"u": user_id},
        )
        .mappings()
        .one_or_none()
    )
    if r is None:
        raise Problema(404, "nenhum número cadastrado")
    if r["confirmado_em"]:
        return
    if r["codigo_hash"] is None or r["codigo_expira_em"] < datetime.now(UTC):
        raise Problema(422, "código expirado; peça um novo")
    if r["tentativas"] >= TENTATIVAS_CODIGO:
        raise Problema(429, "muitas tentativas; peça um novo código")
    if not hmac.compare_digest(r["codigo_hash"], _hash(user_id, codigo.strip(), segredo)):
        conn.execute(
            text("UPDATE whatsapp SET tentativas = tentativas + 1 WHERE user_id = :u"),
            {"u": user_id},
        )
        conn.commit()
        raise Problema(422, "código incorreto")
    conn.execute(
        text(
            "UPDATE whatsapp SET confirmado_em = now(), ativo = true, codigo_hash = NULL, "
            "codigo_expira_em = NULL, tentativas = 0 WHERE user_id = :u"
        ),
        {"u": user_id},
    )


def alterar_whatsapp(conn: Connection, user_id: str, ativo: bool) -> None:
    alterado = conn.execute(
        text("UPDATE whatsapp SET ativo = :a WHERE user_id = :u AND confirmado_em IS NOT NULL"),
        {"a": ativo, "u": user_id},
    ).rowcount
    if not alterado:
        raise Problema(404, "nenhum número confirmado")


def remover_whatsapp(conn: Connection, user_id: str) -> None:
    conn.execute(text("DELETE FROM whatsapp WHERE user_id = :u"), {"u": user_id})


def exportar(conn: Connection, user_id: str) -> dict:
    """Parte da exportação da conta (LGPD)."""
    return {
        "push_aparelhos": [
            dict(r)
            for r in conn.execute(
                text(
                    "SELECT aparelho, endpoint, criado_em FROM push_inscricoes "
                    "WHERE user_id = :u ORDER BY criado_em"
                ),
                {"u": user_id},
            ).mappings()
        ],
        "whatsapp": next(
            (
                dict(r)
                for r in conn.execute(
                    text(
                        "SELECT telefone, confirmado_em, ativo, criado_em FROM whatsapp "
                        "WHERE user_id = :u"
                    ),
                    {"u": user_id},
                ).mappings()
            ),
            None,
        ),
    }

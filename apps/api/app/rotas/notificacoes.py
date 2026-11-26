from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app import notificacoes as nt
from app import schemas as s
from app.config import Settings, get_settings
from app.deps import Conn, Usuario, usuario_obrigatorio
from app.erros import Problema
from app.notificacao import EnviadorPush, EnviadorWhatsApp, push_configurado
from app.whatsapp_config import canal_whatsapp as _canal_whatsapp

router = APIRouter(prefix="/notificacoes", tags=["usuário"])
Logado = Annotated[Usuario, Depends(usuario_obrigatorio)]
Config = Annotated[Settings, Depends(get_settings)]


def canal_push(settings: Config) -> EnviadorPush | None:
    return push_configurado(settings)


def canal_whatsapp(conn: Conn, settings: Config) -> EnviadorWhatsApp | None:
    return _canal_whatsapp(conn, settings)


Push = Annotated[EnviadorPush | None, Depends(canal_push)]
WhatsApp = Annotated[EnviadorWhatsApp | None, Depends(canal_whatsapp)]


def _privado(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


def _estado(conn, usuario: Usuario, settings: Settings, push, wa) -> dict:
    chave = settings.vapid_public_key if push is not None else None
    return nt.estado(conn, usuario.id, chave, wa is not None)


@router.get("", response_model=s.Notificacoes, summary="Canais de notificação do usuário")
def estado(conn: Conn, usuario: Logado, settings: Config, push: Push, wa: WhatsApp, r: Response):
    _privado(r)
    return _estado(conn, usuario, settings, push, wa)


@router.post("/push", status_code=204, summary="Registra o push deste aparelho")
def registrar_push(conn: Conn, usuario: Logado, corpo: s.InscricaoPush, push: Push):
    if push is None:
        raise Problema(503, "push indisponível no momento")
    nt.registrar_push(
        conn, usuario.id, corpo.endpoint, corpo.keys.p256dh, corpo.keys.auth, corpo.aparelho
    )
    conn.commit()
    return Response(status_code=204)


@router.post("/push/cancelar", status_code=204, summary="Desliga o push deste aparelho")
def cancelar_push(conn: Conn, usuario: Logado, corpo: s.CancelamentoPush):
    nt.cancelar_push(conn, usuario.id, corpo.endpoint)
    conn.commit()
    return Response(status_code=204)


@router.delete("/push/{inscricao_id}", status_code=204, summary="Remove um aparelho")
def remover_push(conn: Conn, usuario: Logado, inscricao_id: int):
    nt.remover_push(conn, usuario.id, inscricao_id)
    conn.commit()
    return Response(status_code=204)


@router.post("/push/teste", response_model=s.TestePush, summary="Notificação de teste")
def testar_push(conn: Conn, usuario: Logado, push: Push, r: Response):
    _privado(r)
    if push is None:
        raise Problema(503, "push indisponível no momento")
    return {"enviados": nt.testar_push(conn, usuario.id, push)}


@router.put(
    "/whatsapp", response_model=s.Notificacoes, summary="Cadastra o número e envia o código"
)
def cadastrar_whatsapp(
    conn: Conn,
    usuario: Logado,
    corpo: s.NumeroWhatsApp,
    settings: Config,
    push: Push,
    wa: WhatsApp,
    r: Response,
):
    _privado(r)
    if wa is None:
        raise Problema(503, "WhatsApp indisponível no momento")
    nt.cadastrar_whatsapp(conn, usuario.id, corpo.numero, wa, settings.internal_jwt_secret)
    conn.commit()
    return _estado(conn, usuario, settings, push, wa)


@router.post(
    "/whatsapp/confirmar", response_model=s.Notificacoes, summary="Confirma o número com o código"
)
def confirmar_whatsapp(
    conn: Conn,
    usuario: Logado,
    corpo: s.CodigoWhatsApp,
    settings: Config,
    push: Push,
    wa: WhatsApp,
    r: Response,
):
    _privado(r)
    nt.confirmar_whatsapp(conn, usuario.id, corpo.codigo, settings.internal_jwt_secret)
    conn.commit()
    return _estado(conn, usuario, settings, push, wa)


@router.patch("/whatsapp", response_model=s.Notificacoes, summary="Pausa ou retoma o WhatsApp")
def alterar_whatsapp(
    conn: Conn,
    usuario: Logado,
    corpo: s.AlteracaoWhatsApp,
    settings: Config,
    push: Push,
    wa: WhatsApp,
    r: Response,
):
    _privado(r)
    nt.alterar_whatsapp(conn, usuario.id, corpo.ativo)
    conn.commit()
    return _estado(conn, usuario, settings, push, wa)


@router.delete("/whatsapp", status_code=204, summary="Remove o número")
def remover_whatsapp(conn: Conn, usuario: Logado):
    nt.remover_whatsapp(conn, usuario.id)
    conn.commit()
    return Response(status_code=204)

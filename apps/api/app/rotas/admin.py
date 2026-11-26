from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app import consultas as q
from app import schemas as s
from app import whatsapp_config as wc
from app.config import Settings, get_settings
from app.deps import Conn, Usuario, exigir_admin
from app.erros import Problema
from app.notificacao import FalhaEnvio
from dominio.alertas import AVISO
from dominio.telefone import normalizar_telefone

Admin = Annotated[Usuario, Depends(exigir_admin)]
Config = Annotated[Settings, Depends(get_settings)]

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(exigir_admin)])


@router.get("/execucoes", response_model=s.Execucoes, summary="Histórico do job")
def execucoes(conn: Conn, limite: Annotated[int, Query(ge=1, le=200)] = 50):
    return {"itens": q.execucoes(conn, limite)}


def _privado(r: Response) -> None:
    r.headers["Cache-Control"] = "private, no-store"


@router.get("/whatsapp", response_model=s.ConfigWhatsApp, summary="Instância do WhatsApp")
def ler_whatsapp(conn: Conn, settings: Config, r: Response):
    _privado(r)
    return wc.ler(conn, settings)


@router.put("/whatsapp", response_model=s.ConfigWhatsApp, summary="Salva a instância da Evolution")
def salvar_whatsapp(
    conn: Conn, admin: Admin, settings: Config, corpo: s.NovaConfigWhatsApp, r: Response
):
    _privado(r)
    wc.salvar(conn, settings, admin.id, corpo.url, corpo.instancia, corpo.chave, corpo.ativo)
    conn.commit()
    return wc.ler(conn, settings)


@router.delete("/whatsapp", status_code=204, summary="Remove a instância")
def remover_whatsapp(conn: Conn):
    wc.remover(conn)
    conn.commit()
    return Response(status_code=204)


def _instancia(conn, settings):
    canal = wc.evolution(conn, settings)
    if canal is None:
        raise Problema(404, "nenhuma instância cadastrada")
    return canal


@router.get(
    "/whatsapp/estado", response_model=s.EstadoInstancia, summary="Conexão da instância e QR code"
)
def estado_whatsapp(conn: Conn, settings: Config, r: Response):
    _privado(r)
    canal = _instancia(conn, settings)
    try:
        estado = canal.estado()
        extra = {"qr": None, "codigo_pareamento": None}
        if estado != "open":
            extra = canal.conectar()
        return {"estado": estado, **extra, "erro": None}
    except Exception as e:  # a Evolution fora do ar ou chave errada: mostra no /admin
        motivo = str(e) if isinstance(e, FalhaEnvio) else type(e).__name__
        return {"estado": "erro", "qr": None, "codigo_pareamento": None, "erro": motivo}


@router.post("/whatsapp/teste", status_code=204, summary="Envia uma mensagem de teste")
def testar_whatsapp(conn: Conn, settings: Config, corpo: s.TesteWhatsApp):
    canal = _instancia(conn, settings)
    telefone = normalizar_telefone(corpo.numero)
    if telefone is None:
        raise Problema(422, "número inválido")
    try:
        canal.enviar_texto(
            telefone,
            f"Teste do analisebolsa: a instância está enviando mensagens.\n\n_{AVISO}_",
        )
    except Exception as e:
        motivo = str(e) if isinstance(e, FalhaEnvio) else type(e).__name__
        raise Problema(502, f"a Evolution API não enviou: {motivo}") from e
    return Response(status_code=204)

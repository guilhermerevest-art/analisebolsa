from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app import alertas as al
from app import schemas as s
from app.deps import Conn, Usuario, usuario_obrigatorio
from dominio.alertas import INSIGHTS_ALERTA

router = APIRouter(prefix="/alertas", tags=["usuário"])
Logado = Annotated[Usuario, Depends(usuario_obrigatorio)]
SINAIS = [{"codigo": c, "descricao": d} for c, d in INSIGHTS_ALERTA.items()]


def _privado(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


@router.get("", response_model=s.Alertas, summary="Alertas, últimos disparos e sinais")
def listar(conn: Conn, usuario: Logado, response: Response):
    _privado(response)
    itens = al.listar(conn, usuario.id)
    return {
        "itens": itens,
        "limite": al.LIMITE_ALERTAS,
        "ligados": sum(1 for i in itens if i["ativo"]),
        "disparos": al.disparos(conn, usuario.id),
        "sinais": SINAIS,
    }


@router.get(
    "/carteira", response_model=s.AvisosCarteira, summary="Avisos sobre a carteira e preferências"
)
def avisos_carteira(conn: Conn, usuario: Logado, response: Response):
    _privado(response)
    return al.avisos_carteira(conn, usuario.id)


@router.put("/carteira", status_code=204, summary="Liga ou desliga cada tipo de aviso da carteira")
def salvar_avisos(conn: Conn, usuario: Logado, corpo: s.PreferenciasAvisos):
    al.salvar_preferencias(conn, usuario.id, corpo.model_dump())
    conn.commit()
    return Response(status_code=204)


@router.post("", response_model=s.Alerta, status_code=201, summary="Cria um alerta")
def criar(conn: Conn, usuario: Logado, corpo: s.NovoAlerta, response: Response):
    _privado(response)
    alerta = al.criar(conn, usuario.id, corpo.ticker, corpo.tipo, corpo.parametro, corpo.codigo)
    conn.commit()
    return alerta


@router.patch("/{alerta_id}", response_model=s.Alerta, summary="Liga ou desliga")
def alterar(
    conn: Conn, usuario: Logado, alerta_id: int, corpo: s.AlteracaoAlerta, response: Response
):
    _privado(response)
    alerta = al.alterar(conn, usuario.id, alerta_id, corpo.ativo)
    conn.commit()
    return alerta


@router.delete("/{alerta_id}", status_code=204, summary="Exclui um alerta")
def excluir(conn: Conn, usuario: Logado, alerta_id: int):
    al.excluir(conn, usuario.id, alerta_id)
    conn.commit()
    return Response(status_code=204)

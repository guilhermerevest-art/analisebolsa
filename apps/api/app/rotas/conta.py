from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response

from app import alertas as al
from app.deps import Conn, Usuario, usuario_obrigatorio

router = APIRouter(prefix="/conta", tags=["usuário"])
Logado = Annotated[Usuario, Depends(usuario_obrigatorio)]


@router.get("/exportar", response_model=dict[str, Any], summary="Todos os dados do usuário")
def exportar(conn: Conn, usuario: Logado, response: Response):
    response.headers["Cache-Control"] = "private, no-store"
    return al.exportar(conn, usuario.id)


@router.delete("", status_code=204, summary="Exclui a conta e todos os dados")
def excluir(conn: Conn, usuario: Logado):
    al.excluir_conta(conn, usuario.id)
    conn.commit()
    return Response(status_code=204)

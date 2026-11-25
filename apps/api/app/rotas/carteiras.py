from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response

from app import carteira as c
from app import schemas as s
from app.deps import Conn, Usuario, usuario_obrigatorio
from app.erros import Problema

router = APIRouter(prefix="/carteiras", tags=["usuário"])
Logado = Annotated[Usuario, Depends(usuario_obrigatorio)]
CarteiraId = Annotated[int, Path(ge=1)]
OperacaoId = Annotated[int, Path(ge=1)]


def _privado(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


def _dados(op: s.NovaOperacao) -> dict:
    if op.data > date.today():
        raise Problema(422, "a data da operação não pode ser no futuro")
    return op.model_dump() | {"ticker": op.ticker.upper()}


@router.get("", response_model=s.Carteiras, summary="Carteiras do usuário")
def listar(conn: Conn, usuario: Logado, response: Response):
    _privado(response)
    return {"itens": c.listar(conn, usuario.id), "limite": c.LIMITE_CARTEIRAS}


@router.post("", response_model=s.Carteira, status_code=201, summary="Cria uma carteira")
def criar(conn: Conn, usuario: Logado, corpo: s.NovaCarteira):
    nova = c.criar(conn, usuario.id, corpo.nome.strip())
    conn.commit()
    return nova


@router.patch("/{carteira_id}", response_model=s.Carteira, summary="Renomeia a carteira")
def renomear(conn: Conn, usuario: Logado, carteira_id: CarteiraId, corpo: s.NovaCarteira):
    linha = c.renomear(conn, usuario.id, carteira_id, corpo.nome.strip())
    conn.commit()
    return linha


@router.delete("/{carteira_id}", status_code=204, summary="Exclui a carteira e as operações")
def excluir(conn: Conn, usuario: Logado, carteira_id: CarteiraId):
    c.excluir(conn, usuario.id, carteira_id)
    conn.commit()


@router.get("/{carteira_id}/operacoes", response_model=s.Operacoes, summary="Operações")
def operacoes(conn: Conn, usuario: Logado, carteira_id: CarteiraId, response: Response):
    _privado(response)
    c.obter(conn, usuario.id, carteira_id)
    return {"itens": c.operacoes(conn, carteira_id)}


@router.post(
    "/{carteira_id}/operacoes",
    response_model=s.OperacaoCarteira,
    status_code=201,
    summary="Lança uma compra ou venda",
)
def lancar(conn: Conn, usuario: Logado, carteira_id: CarteiraId, corpo: s.NovaOperacao):
    nova = c.lancar(conn, usuario.id, carteira_id, _dados(corpo))
    conn.commit()
    return nova


@router.put(
    "/{carteira_id}/operacoes/{operacao_id}",
    response_model=s.OperacaoCarteira,
    summary="Edita uma operação",
)
def editar(
    conn: Conn,
    usuario: Logado,
    carteira_id: CarteiraId,
    operacao_id: OperacaoId,
    corpo: s.NovaOperacao,
):
    linha = c.editar(conn, usuario.id, carteira_id, operacao_id, _dados(corpo))
    conn.commit()
    return linha


@router.delete(
    "/{carteira_id}/operacoes/{operacao_id}", status_code=204, summary="Exclui uma operação"
)
def remover(conn: Conn, usuario: Logado, carteira_id: CarteiraId, operacao_id: OperacaoId):
    c.remover(conn, usuario.id, carteira_id, operacao_id)
    conn.commit()


@router.get(
    "/{carteira_id}/resumo",
    response_model=s.ResumoCarteira,
    summary="Posições, proventos recebidos, alocação e resultado",
)
def resumo(conn: Conn, usuario: Logado, carteira_id: CarteiraId, response: Response):
    _privado(response)
    return c.resumo(conn, usuario.id, carteira_id, date.today())


@router.get(
    "/{carteira_id}/rentabilidade",
    response_model=s.RentabilidadeCarteira,
    summary="Rentabilidade acumulada (TWR) contra CDI e Ibovespa",
)
def rentabilidade(conn: Conn, usuario: Logado, carteira_id: CarteiraId, response: Response):
    _privado(response)
    return c.rentabilidade(conn, usuario.id, carteira_id)

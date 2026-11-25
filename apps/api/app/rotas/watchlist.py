from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app import consultas as q
from app import schemas as s
from app import usuario as u
from app.deps import Conn, Ticker, Usuario, usuario_obrigatorio

router = APIRouter(prefix="/watchlist", tags=["usuário"])
Logado = Annotated[Usuario, Depends(usuario_obrigatorio)]


@router.get("", response_model=s.Watchlist, summary="Ativos da watchlist, com as métricas")
def listar(conn: Conn, usuario: Logado, response: Response):
    response.headers["Cache-Control"] = "private, no-store"
    return {"itens": u.watchlist(conn, usuario.id), "limite": u.LIMITE_WATCHLIST}


@router.get("/{ticker}", response_model=s.EstadoWatchlist, summary="O ativo está na watchlist?")
def estado(conn: Conn, usuario: Logado, ticker: Ticker, response: Response):
    response.headers["Cache-Control"] = "private, no-store"
    ativo = q.ativo_por_ticker(conn, ticker)
    return {
        "ticker": ticker,
        "na_lista": u.na_watchlist(conn, usuario.id, ativo["ativo_id"]) is not None,
    }


@router.put("/{ticker}", response_model=s.EstadoWatchlist, summary="Adiciona à watchlist")
def adicionar(conn: Conn, usuario: Logado, ticker: Ticker):
    ativo = q.ativo_por_ticker(conn, ticker)
    u.adicionar_watchlist(conn, usuario.id, ativo["ativo_id"])
    conn.commit()
    return {"ticker": ticker, "na_lista": True}


@router.delete("/{ticker}", response_model=s.EstadoWatchlist, summary="Remove da watchlist")
def remover(conn: Conn, usuario: Logado, ticker: Ticker):
    ativo = q.ativo_por_ticker(conn, ticker)
    u.remover_watchlist(conn, usuario.id, ativo["ativo_id"])
    conn.commit()
    return {"ticker": ticker, "na_lista": False}

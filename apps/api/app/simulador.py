"""Simulador de aportes: carrega preços, proventos e índices e chama o domínio."""

from datetime import date

from sqlalchemy import Connection

from app import consultas as q
from app.carteira import _indice, _precos, _proventos_e_eventos
from dominio import simulador as sim

DESDE_SEMPRE = date(1900, 1, 1)


def simular(
    conn: Connection,
    ticker: str | None,
    inicio: date,
    aporte_inicial: float,
    aporte_mensal: float,
    reinvestir: bool,
) -> dict:
    precos = proventos = None
    if ticker:
        q.ativo_por_ticker(conn, ticker)  # 404 se não existir
        precos = _precos(conn, [ticker], DESDE_SEMPRE).get(ticker, {})
        proventos = _proventos_e_eventos(conn, [ticker]).get(ticker, [])
    cdi = _indice(conn, "cdi", inicio)
    ipca = _indice(conn, "ipca", date(inicio.year, inicio.month, 1))
    pontos = sim.simular(
        inicio,
        aporte_inicial,
        aporte_mensal,
        precos=precos,
        proventos=proventos or [],
        cdi=cdi,
        ipca=ipca,
        reinvestir=reinvestir,
    )
    faixa = None
    if ticker and pontos:
        faixa = sim.faixa_simulada(
            sim.retornos_mensais(precos, proventos),
            [p.data for p in pontos],
            aporte_inicial,
            aporte_mensal,
            sim.semente(ticker, inicio, aporte_inicial, aporte_mensal),
        )
    return {
        "ticker": ticker,
        "inicio": pontos[0].data.replace(day=1) if pontos else None,
        "fim": pontos[-1].data if pontos else None,
        "ipca_ate": max(ipca) if ipca else None,
        "pontos": pontos,
        "faixa": (
            {
                "trajetorias": sim.TRAJETORIAS,
                "meses_historico": faixa.meses_historico,
                "explicacao": sim.EXPLICACAO_FAIXA,
                "pontos": faixa.pontos,
            }
            if faixa
            else None
        ),
        "aviso": sim.AVISO,
    }

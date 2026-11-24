"""Cadeia de fontes: tenta cada uma na ordem até obter um resultado não vazio."""

import logging
from collections.abc import Callable, Sequence
from datetime import date
from typing import TypeVar

from app.config import Settings
from dominio.modelos import AtivoInfo, Candle, Fundamentos, Provento
from fontes.base import ClienteHttp, ErroFonte, FonteDados
from fontes.brapi import BrapiFonte
from fontes.yahoo import YahooFonte

log = logging.getLogger(__name__)
T = TypeVar("T")


class CadeiaFontes:
    def __init__(
        self,
        cotacoes: Sequence[FonteDados],
        proventos: Sequence[FonteDados],
        catalogo: Sequence[FonteDados],
        fundamentos: Sequence[FonteDados],
    ) -> None:
        self._cotacoes = cotacoes
        self._proventos = proventos
        self._catalogo = catalogo
        self._fundamentos = fundamentos

    @staticmethod
    def _primeiro(fontes: Sequence[FonteDados], chamada: Callable[[FonteDados], T]) -> T | None:
        erros: list[str] = []
        for fonte in fontes:
            try:
                resultado = chamada(fonte)
            except ErroFonte as e:
                log.warning("fonte %s falhou: %s", fonte.nome, e)
                erros.append(f"{fonte.nome}: {e}")
                continue
            if resultado:
                return resultado
        if erros and len(erros) == len(fontes):
            raise ErroFonte("; ".join(erros))
        return None

    def listar_ativos(self) -> list[AtivoInfo]:
        return self._primeiro(self._catalogo, lambda f: f.listar_ativos()) or []

    def cotacoes(self, ticker: str, inicio: date, fim: date) -> list[Candle]:
        return self._primeiro(self._cotacoes, lambda f: f.cotacoes(ticker, inicio, fim)) or []

    def proventos(self, ticker: str) -> list[Provento]:
        return self._primeiro(self._proventos, lambda f: f.proventos(ticker)) or []

    def fundamentos(self, ticker: str) -> Fundamentos | None:
        return self._primeiro(self._fundamentos, lambda f: f.fundamentos(ticker))


def criar_cadeia(settings: Settings) -> CadeiaFontes:
    http = ClienteHttp(timeout_s=settings.http_timeout_s)
    disponiveis: dict[str, FonteDados] = {
        "yahoo": YahooFonte(http),
        "brapi": BrapiFonte(http, token=settings.brapi_token),
    }

    def montar(nomes: list[str]) -> list[FonteDados]:
        desconhecidas = set(nomes) - disponiveis.keys()
        if desconhecidas:
            raise ValueError(f"fontes desconhecidas: {sorted(desconhecidas)}")
        # Sem token, a brapi só responde a poucos tickers de teste; tentar cada
        # ativo nela antes do Yahoo só gastaria requisições.
        if not settings.brapi_token and len(nomes) > 1:
            nomes = [n for n in nomes if n != "brapi"]
        return [disponiveis[n] for n in nomes]

    return CadeiaFontes(
        cotacoes=montar(settings.lista_fontes_cotacoes),
        proventos=montar(settings.lista_fontes_proventos),
        catalogo=[disponiveis["brapi"]],
        fundamentos=[disponiveis["brapi"]],
    )

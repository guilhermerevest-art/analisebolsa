"""Contrato das fontes de dados e cliente HTTP com retentativas."""

import time
from collections.abc import Callable
from datetime import date
from typing import Protocol

import httpx

from dominio.modelos import AtivoInfo, Candle, Fundamentos, Provento

USER_AGENT = "Mozilla/5.0 (compatible; analisebolsa/0.1)"
STATUS_RETENTAVEIS = frozenset({429, 500, 502, 503, 504})


class ErroFonte(Exception):
    """Falha ao consultar uma fonte (rede, HTTP ou formato inesperado)."""


class FonteDados(Protocol):
    nome: str

    def listar_ativos(self) -> list[AtivoInfo]: ...
    def cotacoes(self, ticker: str, inicio: date, fim: date) -> list[Candle]: ...
    def proventos(self, ticker: str) -> list[Provento]: ...
    def fundamentos(self, ticker: str) -> Fundamentos | None: ...


class ClienteHttp:
    """GET com até 3 tentativas e backoff exponencial em 429, 5xx e erros de rede."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        *,
        tentativas: int = 3,
        backoff_s: float = 1.0,
        dormir: Callable[[float], None] = time.sleep,
        timeout_s: float = 20.0,
    ) -> None:
        self.client = client or httpx.Client(
            timeout=timeout_s, headers={"User-Agent": USER_AGENT}, follow_redirects=True
        )
        self.tentativas = tentativas
        self.backoff_s = backoff_s
        self.dormir = dormir

    def get_json(
        self, url: str, *, params: dict | None = None, headers: dict | None = None
    ) -> tuple[int, dict]:
        """Devolve (status, json). Status 4xx não retentáveis voltam para quem
        chamou decidir; falhas esgotadas levantam ErroFonte."""
        ultimo_erro: Exception | None = None
        for tentativa in range(self.tentativas):
            if tentativa:
                self.dormir(self.backoff_s * 2 ** (tentativa - 1))
            try:
                resp = self.client.get(url, params=params, headers=headers)
            except httpx.HTTPError as e:
                ultimo_erro = e
                continue
            if resp.status_code in STATUS_RETENTAVEIS:
                ultimo_erro = ErroFonte(f"HTTP {resp.status_code} em {url}")
                continue
            try:
                return resp.status_code, resp.json()
            except ValueError as e:
                raise ErroFonte(f"resposta não é JSON em {url}") from e
        raise ErroFonte(f"falha após {self.tentativas} tentativas: {ultimo_erro}")

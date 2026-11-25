"""Séries do Banco Central (SGS): CDI diário (12) e IPCA mensal (433). API pública, sem chave."""

from datetime import date, datetime, timedelta

from fontes.base import ClienteHttp, ErroFonte

URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
CODIGOS = {"cdi": 12, "ipca": 433}
# O SGS aceita no máximo 10 anos por consulta em séries diárias.
JANELA = timedelta(days=365 * 5)


def janelas(inicio: date, fim: date) -> list[tuple[date, date]]:
    saida, d = [], inicio
    while d <= fim:
        ate = min(d + JANELA, fim)
        saida.append((d, ate))
        d = ate + timedelta(days=1)
    return saida


def parse(dados) -> list[tuple[date, float]]:
    if not isinstance(dados, list):
        raise ErroFonte(f"bcb: resposta inesperada: {str(dados)[:200]}")
    return [
        (datetime.strptime(item["data"], "%d/%m/%Y").date(), float(item["valor"]))
        for item in dados
        if item.get("valor") not in (None, "")
    ]


class BcbFonte:
    nome = "bcb"

    def __init__(self, http: ClienteHttp | None = None) -> None:
        self.http = http or ClienteHttp()

    def serie(self, serie: str, inicio: date, fim: date) -> list[tuple[date, float]]:
        saida: dict[date, float] = {}
        for de, ate in janelas(inicio, fim):
            status, dados = self.http.get_json(
                URL.format(codigo=CODIGOS[serie]),
                params={
                    "formato": "json",
                    "dataInicial": de.strftime("%d/%m/%Y"),
                    "dataFinal": ate.strftime("%d/%m/%Y"),
                },
            )
            if status == 404:  # janela sem dados
                continue
            if status >= 400:
                raise ErroFonte(f"bcb: HTTP {status} na série {serie}")
            saida.update(parse(dados))
        return sorted(saida.items())

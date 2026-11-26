"""Cotas diárias de fundos (informe diário da CVM, dados abertos).

Um arquivo zip por mês (a partir de 2021), com uma linha por fundo e dia. A coluna do CNPJ é
CNPJ_FUNDO_CLASSE nos arquivos novos e CNPJ_FUNDO nos antigos.
"""

import csv
import io
import zipfile
from datetime import date

import httpx

from fontes.base import ErroFonte

URL = "https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/inf_diario_fi_{ano}{mes:02d}.zip"
INICIO = date(2021, 1, 1)


def parse_mes(conteudo: bytes, cnpjs: set[str]) -> list[tuple[str, date, float]]:
    """(cnpj só com dígitos, data, cota) dos fundos pedidos; a primeira classe de cada dia."""
    try:
        arquivo = zipfile.ZipFile(io.BytesIO(conteudo))
    except zipfile.BadZipFile as e:
        raise ErroFonte("cvm: arquivo não é zip") from e
    saida: dict[tuple[str, date], float] = {}
    for nome in arquivo.namelist():
        with arquivo.open(nome) as f:
            leitor = csv.DictReader(io.TextIOWrapper(f, encoding="latin-1"), delimiter=";")
            for linha in leitor:
                bruto = linha.get("CNPJ_FUNDO_CLASSE") or linha.get("CNPJ_FUNDO") or ""
                cnpj = "".join(c for c in bruto if c.isdigit())
                if cnpj not in cnpjs:
                    continue
                try:
                    chave = (cnpj, date.fromisoformat(linha["DT_COMPTC"]))
                    cota = float(linha["VL_QUOTA"])
                except (KeyError, ValueError):
                    continue
                if cota > 0:
                    saida.setdefault(chave, cota)
    return [(c, d, v) for (c, d), v in sorted(saida.items())]


class CvmFonte:
    nome = "cvm"

    def __init__(self, cliente: httpx.Client | None = None) -> None:
        self.cliente = cliente or httpx.Client(timeout=120, follow_redirects=True)

    def mes(self, ano: int, mes: int, cnpjs: set[str]) -> list[tuple[str, date, float]]:
        r = self.cliente.get(URL.format(ano=ano, mes=mes))
        if r.status_code == 404:
            return []
        if r.status_code >= 400:
            raise ErroFonte(f"cvm: HTTP {r.status_code} em {ano}-{mes:02d}")
        return parse_mes(r.content, cnpjs)

"""Catálogo, fundamentos e proventos (fonte primária) e fallback de cotações."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from dominio.modelos import AtivoInfo, Candle, Fundamentos, Provento
from fontes.base import ClienteHttp, ErroFonte

BASE = "https://brapi.dev/api"
CASAS = Decimal("0.0001")
FUSO_B3 = timedelta(hours=-3)

TIPOS_POR_SUBTIPO = {
    "stock": "acao",
    "unit": "acao",
    "fii": "fii",
    "fi-infra": "fii",
    "fi-agro": "fii",
    "etf": "etf",
    "bdr": "bdr",
}
TIPOS_PROVENTO = {
    "DIVIDENDO": "dividendo",
    "JCP": "jcp",
    "JRS CAP PROPRIO": "jcp",
    "RENDIMENTO": "rendimento",
    "DESDOBRAMENTO": "desdobramento",
    "GRUPAMENTO": "grupamento",
    "BONIFICACAO": "bonificacao",
}
# range da brapi que cobre `dias` corridos
RANGES = [(5, "5d"), (30, "1mo"), (90, "3mo"), (180, "6mo"), (365, "1y"), (730, "2y"),
          (1825, "5y"), (3650, "10y")]  # fmt: skip


def _data_iso(valor: str | None) -> date | None:
    if not valor:
        return None
    return (datetime.fromisoformat(valor.replace("Z", "+00:00")) + FUSO_B3).date()


def _pct(valor: float | None) -> float | None:
    return None if valor is None else round(valor * 100, 4)


class BrapiFonte:
    nome = "brapi"

    def __init__(self, http: ClienteHttp | None = None, token: str = "") -> None:
        self.http = http or ClienteHttp()
        self.headers = {"Authorization": f"Bearer {token}"} if token else None

    def _get(self, caminho: str, params: dict | None = None) -> dict | None:
        status, dados = self.http.get_json(f"{BASE}{caminho}", params=params, headers=self.headers)
        if status == 404:
            return None
        if status >= 400:
            raise ErroFonte(f"brapi HTTP {status} em {caminho}: {dados.get('message')}")
        return dados

    def _quote(self, ticker: str, params: dict) -> dict | None:
        dados = self._get(f"/quote/{ticker}", params)
        resultados = (dados or {}).get("results") or []
        return resultados[0] if resultados else None

    # catálogo
    def listar_ativos(self) -> list[AtivoInfo]:
        ativos: dict[str, AtivoInfo] = {}
        pagina = 1
        while True:
            dados = self._get("/quote/list", {"page": pagina, "limit": 100}) or {}
            ativos.update((a.ticker, a) for a in self.parse_lista(dados))
            if not dados.get("hasNextPage"):
                break
            pagina += 1
        return sorted(ativos.values(), key=lambda a: a.ticker)

    @staticmethod
    def parse_lista(dados: dict) -> list[AtivoInfo]:
        saida = []
        for s in dados.get("stocks") or []:
            ticker = (s.get("stock") or "").upper()
            tipo = TIPOS_POR_SUBTIPO.get(s.get("subType") or s.get("type") or "")
            if tipo is None or not (4 <= len(ticker) <= 6) or not ticker.isalnum():
                continue
            saida.append(
                AtivoInfo(
                    ticker=ticker,
                    nome=s.get("name") or ticker,
                    tipo=tipo,
                    setor=s.get("sector"),
                    segmento=s.get("subsector"),
                    logo_url=s.get("logo"),
                )
            )
        return saida

    # cotações
    def cotacoes(self, ticker: str, inicio: date, fim: date) -> list[Candle]:
        dias = (date.today() - inicio).days + 1
        faixa = next((r for limite, r in RANGES if dias <= limite), "max")
        r = self._quote(ticker, {"range": faixa, "interval": "1d"})
        return self.parse_cotacoes(r, inicio, fim) if r else []

    @staticmethod
    def parse_cotacoes(r: dict, inicio: date, fim: date) -> list[Candle]:
        por_data: dict[date, Candle] = {}
        for h in r.get("historicalDataPrice") or []:
            valores = (h.get("open"), h.get("high"), h.get("low"), h.get("close"))
            if any(v is None for v in valores):
                continue
            d = (datetime.fromtimestamp(h["date"], UTC) + FUSO_B3).date()
            if not inicio <= d <= fim:
                continue
            o, hi, lo, c = (Decimal(str(v)).quantize(CASAS) for v in valores)
            aj = h.get("adjustedClose")
            aj = Decimal(str(aj)).quantize(CASAS) if aj is not None else c
            por_data[d] = Candle(d, o, hi, lo, c, aj, int(h.get("volume") or 0))
        return [por_data[d] for d in sorted(por_data)]

    # proventos
    def proventos(self, ticker: str) -> list[Provento]:
        r = self._quote(ticker, {"dividends": "true"})
        return self.parse_proventos(r) if r else []

    @staticmethod
    def parse_proventos(r: dict) -> list[Provento]:
        dd = r.get("dividendsData") or {}
        saida: dict[tuple[str, date], Provento] = {}
        for item in dd.get("cashDividends") or []:
            tipo = TIPOS_PROVENTO.get((item.get("label") or "").upper())
            data_com = _data_iso(item.get("lastDatePrior"))
            if tipo is None or data_com is None or item.get("rate") is None:
                continue
            valor = Decimal(str(item["rate"]))
            if (tipo, data_com) in saida:  # parcelas na mesma data-com: soma
                valor += saida[(tipo, data_com)].valor
            saida[(tipo, data_com)] = Provento(
                tipo, data_com, valor, _data_iso(item.get("paymentDate"))
            )
        for item in dd.get("stockDividends") or []:
            tipo = TIPOS_PROVENTO.get((item.get("label") or "").upper())
            data_com = _data_iso(item.get("lastDatePrior"))
            if tipo is None or data_com is None or item.get("factor") is None:
                continue
            saida[(tipo, data_com)] = Provento(tipo, data_com, Decimal(str(item["factor"])))
        return sorted(saida.values(), key=lambda p: (p.data_com, p.tipo))

    # fundamentos
    def fundamentos(self, ticker: str) -> Fundamentos | None:
        r = self._quote(
            ticker,
            {"fundamental": "true", "modules": "defaultKeyStatistics,financialData"},
        )
        return self.parse_fundamentos(r, date.today()) if r else None

    @staticmethod
    def parse_fundamentos(r: dict, referencia: date) -> Fundamentos:
        ks = r.get("defaultKeyStatistics") or {}
        fd = r.get("financialData") or {}
        div_liq_ebitda = None
        if fd.get("ebitda") and fd.get("totalDebt") is not None:
            liquida = fd["totalDebt"] - (fd.get("totalCash") or 0)
            div_liq_ebitda = round(liquida / fd["ebitda"], 4)
        mercado = r.get("marketCap") or ks.get("marketCap")
        return Fundamentos(
            data_referencia=referencia,
            pl=r.get("priceEarnings") or ks.get("trailingPE"),
            pvp=ks.get("priceToBook"),
            dy_12m=_pct(ks.get("dividendYield")),
            roe=_pct(fd.get("returnOnEquity")),
            margem_liquida=_pct(fd.get("profitMargins") or ks.get("profitMargins")),
            div_liq_ebitda=div_liq_ebitda,
            vpa=ks.get("bookValue"),
            lpa=r.get("earningsPerShare") or ks.get("trailingEps"),
            valor_mercado=Decimal(str(round(mercado, 2))) if mercado else None,
            extras={
                k: v
                for k, v in {
                    "beta": ks.get("beta"),
                    "ev_ebitda": ks.get("enterpriseToEbitda"),
                    "margem_ebitda": _pct(fd.get("ebitdaMargins")),
                }.items()
                if v is not None
            },
        )

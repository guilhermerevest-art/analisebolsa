"""Fonte primária de cotações e fallback de proventos (endpoint chart, sufixo .SA)."""

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from dominio.modelos import AtivoInfo, Candle, Fundamentos, Provento
from fontes.base import ClienteHttp, ErroFonte

URL = "https://query2.finance.yahoo.com/v8/finance/chart/{simbolo}"
CASAS = Decimal("0.0001")


def _dec(valor: float) -> Decimal:
    return Decimal(str(valor)).quantize(CASAS)


def _epoch(d: date) -> int:
    return int(datetime.combine(d, time.min, tzinfo=UTC).timestamp())


def _dia_util_anterior(d: date) -> date:
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


class YahooFonte:
    nome = "yahoo"

    def __init__(self, http: ClienteHttp | None = None) -> None:
        self.http = http or ClienteHttp()

    def _chart(self, ticker: str, params: dict) -> dict | None:
        status, dados = self.http.get_json(URL.format(simbolo=f"{ticker}.SA"), params=params)
        chart = dados.get("chart") or {}
        if status == 404 or not chart.get("result"):
            if status == 404 or (chart.get("error") or {}).get("code") == "Not Found":
                return None
            raise ErroFonte(f"yahoo: resposta inesperada para {ticker}: {chart.get('error')}")
        return chart["result"][0]

    def _chart_periodo(self, ticker: str, inicio: date, fim: date) -> dict | None:
        return self._chart(
            ticker,
            {
                "period1": _epoch(inicio),
                "period2": _epoch(fim + timedelta(days=1)),
                "interval": "1d",
                "events": "div,splits",
                "includeAdjustedClose": "true",
            },
        )

    def listar_ativos(self) -> list[AtivoInfo]:
        return []

    def fundamentos(self, ticker: str) -> Fundamentos | None:
        return None

    def cotacoes(self, ticker: str, inicio: date, fim: date) -> list[Candle]:
        r = self._chart_periodo(ticker, inicio, fim)
        return self.parse_cotacoes(r, inicio, fim) if r else []

    def proventos(self, ticker: str) -> list[Provento]:
        r = self._chart(ticker, {"range": "max", "interval": "1mo", "events": "div,splits"})
        return self.parse_proventos(r) if r else []

    @staticmethod
    def parse_cotacoes(r: dict, inicio: date, fim: date) -> list[Candle]:
        offset = timedelta(seconds=(r.get("meta") or {}).get("gmtoffset", -10800))
        stamps = r.get("timestamp") or []
        ind = r.get("indicators") or {}
        q = (ind.get("quote") or [{}])[0]
        adj = ((ind.get("adjclose") or [{}])[0]).get("adjclose") or q.get("close") or []
        por_data: dict[date, Candle] = {}
        for i, ts in enumerate(stamps):
            valores = (q["open"][i], q["high"][i], q["low"][i], q["close"][i], adj[i])
            if any(v is None for v in valores):
                continue
            d = (datetime.fromtimestamp(ts, UTC) + offset).date()
            if not inicio <= d <= fim:
                continue
            o, h, lo, c, a = (_dec(v) for v in valores)
            por_data[d] = Candle(d, o, h, lo, c, a, int(q["volume"][i] or 0))
        return [por_data[d] for d in sorted(por_data)]

    @staticmethod
    def parse_proventos(r: dict) -> list[Provento]:
        offset = timedelta(seconds=(r.get("meta") or {}).get("gmtoffset", -10800))
        eventos = r.get("events") or {}
        saida: dict[tuple[str, date], Provento] = {}
        for ev in (eventos.get("dividends") or {}).values():
            data_ex = (datetime.fromtimestamp(ev["date"], UTC) + offset).date()
            data_com = _dia_util_anterior(data_ex)
            chave = ("dividendo", data_com)
            valor = Decimal(str(ev["amount"]))
            if chave in saida:  # dois pagamentos na mesma data-com: soma
                valor += saida[chave].valor
            saida[chave] = Provento("dividendo", data_com, valor)
        for ev in (eventos.get("splits") or {}).values():
            data_ex = (datetime.fromtimestamp(ev["date"], UTC) + offset).date()
            fator = Decimal(str(ev["numerator"])) / Decimal(str(ev["denominator"]))
            tipo = "desdobramento" if fator > 1 else "grupamento"
            data_com = _dia_util_anterior(data_ex)
            saida[(tipo, data_com)] = Provento(tipo, data_com, fator.quantize(Decimal("1e-8")))
        return sorted(saida.values(), key=lambda p: (p.data_com, p.tipo))

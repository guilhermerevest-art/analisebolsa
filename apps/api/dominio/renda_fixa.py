"""Renda fixa e fundos: valor atualizado, IR regressivo e líquido (puro, sem I/O).

- Pós-fixado (% do CDI): cada dia útil rende CDI do dia × percentual.
- Prefixado: (1 + taxa)^(dias úteis / 252).
- IPCA +: IPCA de cada mês completo depois da aplicação × (1 + taxa)^(dias úteis / 252).
  O IPCA do mês corrente ainda não saiu: é uma aproximação.
- Dias úteis: os dias com CDI (calendário da B3); depois do último CDI conhecido, os dias de
  semana.
- IR regressivo sobre o ganho, pelos dias corridos: até 180 dias 22,5%, até 360 20%, até
  720 17,5%, depois 15%. LCI, LCA e quem marcar isento não pagam. IOF (só nos primeiros 30
  dias) e taxas de custódia ficam de fora.
- Fundos: cotas × última cota da CVM. O IR do fundo (come-cotas e no resgate) não é
  descontado: o valor é bruto.
"""

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from datetime import date, timedelta

COTA_PROXIMA_DIAS = 7

TIPOS = {
    "cdb": "CDB",
    "lci_lca": "LCI/LCA",
    "tesouro": "Tesouro Direto",
    "debenture": "Debênture",
    "outro_rf": "Outro de renda fixa",
    "fundo": "Fundo de investimento",
}


@dataclass(frozen=True, slots=True)
class Investimento:
    tipo: str
    data_aplicacao: date
    valor_aplicado: float
    indexador: str | None = None
    taxa: float | None = None
    isento_ir: bool = False
    cotas: float | None = None
    resgate_data: date | None = None
    resgate_valor: float | None = None


@dataclass(frozen=True, slots=True)
class Avaliacao:
    data: date
    bruto: float | None
    ir: float | None
    liquido: float | None
    rendimento: float | None  # % líquido sobre o aplicado (bruto para fundos)
    aliquota: float | None  # % do IR regressivo aplicável hoje
    cotas: float | None = None
    observacao: str | None = None


def aliquota_ir(dias: int) -> float:
    if dias <= 180:
        return 22.5
    if dias <= 360:
        return 20.0
    if dias <= 720:
        return 17.5
    return 15.0


def _dias_uteis(inicio: date, fim: date, calendario: list[date]) -> int:
    """Dias úteis em (inicio, fim]: os do calendário do CDI e, depois dele, os dias de semana."""
    n = bisect_right(calendario, fim) - bisect_right(calendario, inicio)
    d = max(inicio, calendario[-1] if calendario else inicio) + timedelta(days=1)
    while d <= fim:
        if d.weekday() < 5:
            n += 1
        d += timedelta(days=1)
    return n


def descrever_taxa(indexador: str | None, taxa: float | None) -> str:
    if indexador is None or taxa is None:
        return ""
    t = f"{taxa:.2f}".rstrip("0").rstrip(".").replace(".", ",")
    if indexador == "cdi":
        return f"{t}% do CDI"
    if indexador == "prefixado":
        return f"{t}% ao ano"
    return f"IPCA + {t}% ao ano"


def avaliar(
    inv: Investimento,
    hoje: date,
    cdi: dict[date, float],
    ipca: dict[date, float],
    cotas_fundo: dict[date, float] | None = None,
) -> Avaliacao:
    ate = inv.resgate_data or hoje
    if inv.resgate_valor is not None:
        bruto = inv.resgate_valor
        return _com_ir(inv, ate, bruto, "Resgatado")

    if inv.tipo == "fundo":
        return _fundo(inv, ate, cotas_fundo or {})

    calendario = sorted(cdi)
    if inv.indexador == "cdi":
        fator = 1.0
        for d in calendario[
            bisect_right(calendario, inv.data_aplicacao) : bisect_right(calendario, ate)
        ]:
            fator *= 1 + cdi[d] / 100 * inv.taxa / 100
    else:
        du = _dias_uteis(inv.data_aplicacao, ate, calendario)
        fator = (1 + inv.taxa / 100) ** (du / 252)
        if inv.indexador == "ipca":
            # Meses completos depois da aplicação até o último IPCA publicado.
            primeiro = date(
                inv.data_aplicacao.year + inv.data_aplicacao.month // 12,
                inv.data_aplicacao.month % 12 + 1,
                1,
            )
            for mes, v in sorted(ipca.items()):
                if primeiro <= mes and mes < date(ate.year, ate.month, 1):
                    fator *= 1 + v / 100
    return _com_ir(inv, ate, inv.valor_aplicado * fator, None)


def _com_ir(inv: Investimento, ate: date, bruto: float, observacao: str | None) -> Avaliacao:
    ganho = max(0.0, bruto - inv.valor_aplicado)
    if inv.tipo == "fundo":
        return Avaliacao(
            ate,
            round(bruto, 2),
            None,
            None,
            (bruto / inv.valor_aplicado - 1) * 100,
            None,
            inv.cotas,
            observacao,
        )
    aliquota = 0.0 if inv.isento_ir else aliquota_ir((ate - inv.data_aplicacao).days)
    ir = round(ganho * aliquota / 100, 2)
    liquido = round(bruto - ir, 2)
    return Avaliacao(
        ate,
        round(bruto, 2),
        ir,
        liquido,
        (liquido / inv.valor_aplicado - 1) * 100,
        aliquota,
        None,
        observacao,
    )


def _fundo(inv: Investimento, ate: date, cotas_fundo: dict[date, float]) -> Avaliacao:
    datas = sorted(d for d in cotas_fundo if d <= ate)
    if not datas:
        return Avaliacao(ate, None, None, None, None, None, inv.cotas, "Aguardando as cotas da CVM")
    cotas = inv.cotas
    if cotas is None:
        # Cota do dia da aplicação (ou a primeira depois dela, se não houve divulgação no dia).
        i = bisect_left(datas, inv.data_aplicacao)
        if i == len(datas):
            return Avaliacao(ate, None, None, None, None, None, None, "Aguardando as cotas da CVM")
        if (datas[i] - inv.data_aplicacao).days > COTA_PROXIMA_DIAS:
            # A CVM não tem a cota perto da aplicação (os arquivos mensais começam em 2021).
            return Avaliacao(ate, None, None, None, None, None, None, "Informe o número de cotas")
        cotas = inv.valor_aplicado / cotas_fundo[datas[i]]
    ultima = datas[-1]
    bruto = cotas * cotas_fundo[ultima]
    return Avaliacao(
        ultima,
        round(bruto, 2),
        None,
        None,
        (bruto / inv.valor_aplicado - 1) * 100,
        None,
        round(cotas, 8),
        None,
    )


def normalizar_cnpj(valor: str) -> str | None:
    """Só os 14 dígitos, se os dígitos verificadores conferem."""
    d = "".join(c for c in valor if c.isdigit())
    if len(d) != 14 or d == d[0] * 14:
        return None

    def dv(base: str, pesos: list[int]) -> str:
        r = sum(int(a) * b for a, b in zip(base, pesos, strict=True)) % 11
        return "0" if r < 2 else str(11 - r)

    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    if dv(d[:12], p1) != d[12] or dv(d[:13], [6, *p1]) != d[13]:
        return None
    return d


def formatar_cnpj(d: str) -> str:
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"

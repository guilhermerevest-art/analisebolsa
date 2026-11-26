"""Imposto de renda sobre ganho de capital em renda variável (puro).

Regras de pessoa física, apuração mensal:

- Ações: 15% sobre o ganho. Isento quando o total de **vendas de ações** do mês fica em até
  R$ 20.000,00. O prejuízo de um mês isento continua compensável.
- ETFs e BDRs: 15%, sem isenção. Entram com as ações no mesmo grupo de compensação.
- FIIs: 20%, sem isenção. Prejuízo de FII só compensa ganho de FII.
- Prejuízo não expira e é compensado nos meses seguintes, no seu grupo.
- IRRF ("dedo-duro"): 0,005% sobre o valor das vendas, dispensado abaixo de R$ 1,00 no mês;
  é descontado do imposto do mês, e o que sobra fica para os meses seguintes.
- Day trade (compra e venda do mesmo ativo no mesmo dia, quantidade casada): 20%, sem
  isenção, com prejuízo próprio (só compensa day trade). IRRF de 1% sobre o resultado
  positivo do dia. As vendas de day trade não contam para o limite de R$ 20 mil. Day trade
  de FII fica no grupo dos FIIs (20%).
- DARF código 6015, vencimento no último dia útil do mês seguinte. Abaixo de R$ 10,00 não se
  paga: o valor passa para o mês seguinte.

Os textos descrevem a conta; não são orientação tributária.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from dominio.carteira import VendaRealizada

ZERO = Decimal(0)
CENTAVO = Decimal("0.01")
LIMITE_ISENCAO_ACOES = Decimal("20000")
ALIQUOTA_COMUM = Decimal("0.15")
ALIQUOTA_FII = Decimal("0.20")
ALIQUOTA_DAY_TRADE = Decimal("0.20")
ALIQUOTA_IRRF_DAY_TRADE = Decimal("0.01")
ALIQUOTA_IRRF = Decimal("0.00005")
IRRF_MINIMO = Decimal("1")
DARF_MINIMO = Decimal("10")
CODIGO_DARF = "6015"

# Dias sem expediente bancário: feriados nacionais fixos e, pela Páscoa, Carnaval (segunda e
# terça), Sexta-feira Santa e Corpus Christi. Em 31/12 os bancos não abrem ao público.
FERIADOS_FIXOS = {
    (1, 1),
    (4, 21),
    (5, 1),
    (9, 7),
    (10, 12),
    (11, 2),
    (11, 15),
    (11, 20),
    (12, 25),
    (12, 31),
}


def pascoa(ano: int) -> date:
    """Domingo de Páscoa (algoritmo de Meeus/Jones/Butcher, calendário gregoriano)."""
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = (h + l - 7 * m + 114) % 31 + 1
    return date(ano, mes, dia)


def dia_util_bancario(dia: date) -> bool:
    if dia.weekday() >= 5 or (dia.month, dia.day) in FERIADOS_FIXOS:
        return False
    p = pascoa(dia.year)
    moveis = {p - timedelta(days=48), p - timedelta(days=47), p - timedelta(days=2)}
    moveis.add(p + timedelta(days=60))
    return dia not in moveis


def _r(v: Decimal) -> Decimal:
    return v.quantize(CENTAVO, ROUND_HALF_UP)


def ultimo_dia_util_do_mes_seguinte(mes: date) -> date:
    """`mes` é qualquer dia do mês de apuração."""
    primeiro_seguinte = date(mes.year + mes.month // 12, mes.month % 12 + 1, 1)
    dia = date(
        primeiro_seguinte.year + primeiro_seguinte.month // 12,
        primeiro_seguinte.month % 12 + 1,
        1,
    ) - timedelta(days=1)
    while not dia_util_bancario(dia):
        dia -= timedelta(days=1)
    return dia


@dataclass(slots=True)
class MesApurado:
    mes: date  # primeiro dia do mês
    vendas_acoes: Decimal = ZERO
    vendas_total: Decimal = ZERO
    isento_acoes: bool = False
    resultado_acoes: Decimal = ZERO
    ganho_isento: Decimal = ZERO  # ganho de ações num mês isento (vai como rendimento isento)
    resultado_etf_bdr: Decimal = ZERO
    resultado_fii: Decimal = ZERO
    resultado_day_trade: Decimal = ZERO
    compensado_comum: Decimal = ZERO
    compensado_fii: Decimal = ZERO
    compensado_day_trade: Decimal = ZERO
    base_comum: Decimal = ZERO
    base_fii: Decimal = ZERO
    base_day_trade: Decimal = ZERO
    imposto_comum: Decimal = ZERO
    imposto_fii: Decimal = ZERO
    imposto_day_trade: Decimal = ZERO
    irrf: Decimal = ZERO
    irrf_usado: Decimal = ZERO
    acumulado_anterior: Decimal = ZERO  # DARF abaixo de R$ 10 vindo dos meses anteriores
    darf: Decimal = ZERO
    vencimento: date | None = None
    fica_para_depois: Decimal = ZERO  # abaixo de R$ 10: passa para o mês seguinte
    prejuizo_comum: Decimal = ZERO  # saldo a compensar depois do mês
    prejuizo_fii: Decimal = ZERO
    prejuizo_day_trade: Decimal = ZERO
    saldo_irrf: Decimal = ZERO

    @property
    def imposto_devido(self) -> Decimal:
        return self.imposto_comum + self.imposto_fii + self.imposto_day_trade


@dataclass(slots=True)
class Apuracao:
    meses: list[MesApurado] = field(default_factory=list)
    day_trade: list[tuple[str, date]] = field(default_factory=list)
    sem_tipo: list[str] = field(default_factory=list)

    @property
    def prejuizo_comum(self) -> Decimal:
        return self.meses[-1].prejuizo_comum if self.meses else ZERO

    @property
    def prejuizo_fii(self) -> Decimal:
        return self.meses[-1].prejuizo_fii if self.meses else ZERO

    @property
    def prejuizo_day_trade(self) -> Decimal:
        return self.meses[-1].prejuizo_day_trade if self.meses else ZERO

    @property
    def pendente(self) -> Decimal:
        return self.meses[-1].fica_para_depois if self.meses else ZERO

    @property
    def saldo_irrf(self) -> Decimal:
        return self.meses[-1].saldo_irrf if self.meses else ZERO


def _compensar(resultado: Decimal, prejuizo: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    """(base tributável, prejuízo usado, novo saldo de prejuízo)."""
    if resultado <= 0:
        return ZERO, ZERO, prejuizo - resultado
    usado = min(prejuizo, resultado)
    return resultado - usado, usado, prejuizo - usado


def apurar(vendas: list[VendaRealizada], tipos: dict[str, str]) -> Apuracao:
    """Apuração mês a mês, só nos meses com venda.

    `tipos`: ticker -> "acao" | "fii" | "etf" | "bdr". As vendas marcadas como day trade
    (ver `dominio.carteira`) vão para o grupo de day trade.
    """
    res = Apuracao()
    por_mes: dict[date, list[VendaRealizada]] = defaultdict(list)
    for v in vendas:
        por_mes[v.data.replace(day=1)].append(v)
        if v.day_trade:
            res.day_trade.append((v.ticker, v.data))
        if v.ticker not in tipos and v.ticker not in res.sem_tipo:
            res.sem_tipo.append(v.ticker)

    prej_comum = prej_fii = prej_dt = saldo_irrf = pendente = ZERO
    for mes in sorted(por_mes):
        m = MesApurado(mes)
        vendas_comuns = ZERO
        dt_por_dia: dict[date, Decimal] = defaultdict(Decimal)
        for v in por_mes[mes]:
            tipo = tipos.get(v.ticker, "acao")
            m.vendas_total += v.valor
            if v.day_trade and tipo != "fii":
                m.resultado_day_trade += v.resultado
                dt_por_dia[v.data] += v.resultado
                continue
            if v.day_trade:  # day trade de FII: grupo dos FIIs
                m.resultado_fii += v.resultado
                dt_por_dia[v.data] += v.resultado
                continue
            vendas_comuns += v.valor
            if tipo == "acao":
                m.vendas_acoes += v.valor
                m.resultado_acoes += v.resultado
            elif tipo == "fii":
                m.resultado_fii += v.resultado
            else:
                m.resultado_etf_bdr += v.resultado
        m.resultado_acoes, m.resultado_etf_bdr, m.resultado_fii, m.resultado_day_trade = (
            _r(m.resultado_acoes),
            _r(m.resultado_etf_bdr),
            _r(m.resultado_fii),
            _r(m.resultado_day_trade),
        )
        m.vendas_acoes, m.vendas_total = _r(m.vendas_acoes), _r(m.vendas_total)

        m.isento_acoes = m.vendas_acoes <= LIMITE_ISENCAO_ACOES
        acoes_tributaveis = m.resultado_acoes
        if m.isento_acoes and m.resultado_acoes > 0:
            m.ganho_isento = m.resultado_acoes
            acoes_tributaveis = ZERO

        # Ações e ETFs/BDRs somam no mesmo grupo antes de compensar.
        m.base_comum, m.compensado_comum, prej_comum = _compensar(
            acoes_tributaveis + m.resultado_etf_bdr, prej_comum
        )
        m.base_fii, m.compensado_fii, prej_fii = _compensar(m.resultado_fii, prej_fii)
        m.base_day_trade, m.compensado_day_trade, prej_dt = _compensar(
            m.resultado_day_trade, prej_dt
        )
        m.imposto_comum = _r(m.base_comum * ALIQUOTA_COMUM)
        m.imposto_fii = _r(m.base_fii * ALIQUOTA_FII)
        m.imposto_day_trade = _r(m.base_day_trade * ALIQUOTA_DAY_TRADE)

        # IRRF: 0,005% das vendas comuns e 1% do resultado positivo de cada dia de day trade.
        irrf = _r(vendas_comuns * ALIQUOTA_IRRF)
        irrf_dt = sum((_r(r * ALIQUOTA_IRRF_DAY_TRADE) for r in dt_por_dia.values() if r > 0), ZERO)
        m.irrf = (irrf if irrf >= IRRF_MINIMO else ZERO) + (
            irrf_dt if irrf_dt >= IRRF_MINIMO else ZERO
        )
        disponivel = saldo_irrf + m.irrf
        m.irrf_usado = min(disponivel, m.imposto_devido)
        saldo_irrf = disponivel - m.irrf_usado

        m.acumulado_anterior = pendente
        a_pagar = m.imposto_devido - m.irrf_usado + pendente
        if a_pagar >= DARF_MINIMO:
            m.darf, pendente = a_pagar, ZERO
            m.vencimento = ultimo_dia_util_do_mes_seguinte(mes)
        else:
            m.darf, pendente = ZERO, a_pagar
        m.fica_para_depois = pendente
        m.prejuizo_comum, m.prejuizo_fii, m.saldo_irrf = prej_comum, prej_fii, saldo_irrf
        m.prejuizo_day_trade = prej_dt
        res.meses.append(m)
    return res

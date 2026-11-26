import type { ChaveGlossario } from "@/lib/glossario";
import type { IndicadorMercado } from "@/lib/tipos-api";

const real = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", minimumFractionDigits: 2, maximumFractionDigits: 4 });
const dolar = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

/** Valor no formato de cada unidade: pontos ("173.353"), reais ("R$ 5,7446"), dólares ("US$ 60.591"). */
export function formatarIndicador(valor: number, unidade: IndicadorMercado["unidade"]): string {
  if (unidade === "reais") return real.format(valor);
  if (unidade === "dolares") return dolar.format(valor);
  return valor.toLocaleString("pt-BR", { maximumFractionDigits: valor >= 10000 ? 0 : 2 });
}

export const TERMO_INDICADOR: Record<string, ChaveGlossario> = {
  ibov: "ibovespa",
  ifix: "ifix",
  smll: "smll",
  idiv: "idiv",
  dolar: "dolar",
  euro: "euro",
  sp500: "sp500",
  bitcoin: "bitcoin",
};

export const PERIODOS = { "1a": { rotulo: "1 ano", anos: 1 }, "5a": { rotulo: "5 anos", anos: 5 }, max: { rotulo: "Desde 2005", anos: 30 } } as const;
export type Periodo = keyof typeof PERIODOS;

export function inicioDoPeriodo(periodo: Periodo, hoje = new Date()): string {
  const d = new Date(hoje);
  d.setUTCFullYear(d.getUTCFullYear() - PERIODOS[periodo].anos);
  const iso = d.toISOString().slice(0, 10);
  return iso < "2005-01-01" ? "2005-01-01" : iso;
}

/** Caminho SVG (0..largura × 0..altura) de uma minissérie, para os cartões. */
export function caminhoMiniatura(valores: number[], largura = 120, altura = 36): string {
  if (valores.length < 2) return "";
  const min = Math.min(...valores);
  const max = Math.max(...valores);
  const faixa = max - min || 1;
  return valores
    .map((v, i) => `${i ? "L" : "M"}${((i / (valores.length - 1)) * largura).toFixed(1)},${(altura - ((v - min) / faixa) * altura).toFixed(1)}`)
    .join("");
}

/** Conversões puras entre a API e o formato do lightweight-charts. */
import type { Candle, IndicadoresDia } from "./tipos-api";

export type Periodo = "1M" | "6M" | "1A" | "5A" | "MAX";
export type Intervalo = "D" | "S" | "M";

export const PERIODOS: Periodo[] = ["1M", "6M", "1A", "5A", "MAX"];
export const INTERVALOS: { valor: Intervalo; rotulo: string; api: "1d" | "1w" | "1M" }[] = [
  { valor: "D", rotulo: "Diário", api: "1d" },
  { valor: "S", rotulo: "Semanal", api: "1w" },
  { valor: "M", rotulo: "Mensal", api: "1M" },
];

const INICIO_HISTORICO = "2000-01-01";

function iso(d: Date): string {
  return d.toISOString().slice(0, 10);
}

/** Data inicial (ISO) de um período, contada a partir de `hoje`. */
export function inicioDoPeriodo(periodo: Periodo, hoje = new Date()): string {
  const d = new Date(Date.UTC(hoje.getUTCFullYear(), hoje.getUTCMonth(), hoje.getUTCDate()));
  switch (periodo) {
    case "1M":
      d.setUTCMonth(d.getUTCMonth() - 1);
      break;
    case "6M":
      d.setUTCMonth(d.getUTCMonth() - 6);
      break;
    case "1A":
      d.setUTCFullYear(d.getUTCFullYear() - 1);
      break;
    case "5A":
      d.setUTCFullYear(d.getUTCFullYear() - 5);
      break;
    case "MAX":
      return INICIO_HISTORICO;
  }
  return iso(d);
}

export type PontoCandle = { time: string; open: number; high: number; low: number; close: number };
export type PontoValor = { time: string; value: number; color?: string };

export function paraCandles(candles: Candle[]): PontoCandle[] {
  return candles.map((c) => ({
    time: c.data,
    open: Number(c.abertura),
    high: Number(c.maxima),
    low: Number(c.minima),
    close: Number(c.fechamento),
  }));
}

export function paraVolume(candles: Candle[], corAlta: string, corBaixa: string): PontoValor[] {
  return candles.map((c) => ({
    time: c.data,
    value: c.volume,
    color: Number(c.fechamento) >= Number(c.abertura) ? corAlta : corBaixa,
  }));
}

type ChaveIndicador = Exclude<keyof IndicadoresDia, "data">;

/** Série de um indicador sem os pontos nulos (aquecimento das médias). */
export function serieIndicador(itens: IndicadoresDia[], chave: ChaveIndicador): PontoValor[] {
  const saida: PontoValor[] = [];
  for (const i of itens) {
    const v = i[chave];
    if (v !== null && v !== undefined && Number.isFinite(v)) saida.push({ time: i.data, value: v });
  }
  return saida;
}

export function histogramaMacd(itens: IndicadoresDia[], corAlta: string, corBaixa: string): PontoValor[] {
  return serieIndicador(itens, "macd_hist").map((p) => ({ ...p, color: p.value >= 0 ? corAlta : corBaixa }));
}

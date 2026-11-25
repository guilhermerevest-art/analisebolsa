import { describe, expect, it } from "vitest";

import { histogramaMacd, inicioDoPeriodo, paraCandles, paraVolume, serieIndicador } from "./grafico";
import type { Candle, IndicadoresDia } from "./tipos-api";

const HOJE = new Date("2026-11-24T15:00:00Z");

describe("períodos", () => {
  it("calcula a data inicial", () => {
    expect(inicioDoPeriodo("1M", HOJE)).toBe("2026-10-24");
    expect(inicioDoPeriodo("6M", HOJE)).toBe("2026-05-24");
    expect(inicioDoPeriodo("1A", HOJE)).toBe("2025-11-24");
    expect(inicioDoPeriodo("5A", HOJE)).toBe("2021-11-24");
    expect(inicioDoPeriodo("MAX", HOJE)).toBe("2000-01-01");
  });
});

const candle = (data: string, o: string, c: string): Candle => ({
  data,
  abertura: o,
  maxima: "50",
  minima: "1",
  fechamento: c,
  fechamento_ajustado: c,
  volume: 100,
});

describe("conversões", () => {
  it("candles viram números com time YYYY-MM-DD", () => {
    expect(paraCandles([candle("2025-06-04", "10.5", "11")])).toEqual([
      { time: "2025-06-04", open: 10.5, high: 50, low: 1, close: 11 },
    ]);
  });

  it("volume colorido pela direção do candle", () => {
    const v = paraVolume([candle("2025-06-04", "10", "11"), candle("2025-06-05", "11", "10")], "verde", "vermelho");
    expect(v.map((p) => p.color)).toEqual(["verde", "vermelho"]);
  });

  it("indicadores descartam nulos do aquecimento", () => {
    const base = { mm20: null, mm50: null, mm200: null, mme9: null, rsi14: null, macd: null, macd_sinal: null, macd_hist: null, bb_superior: null, bb_inferior: null, atr14: null, vol_media20: null };
    const itens: IndicadoresDia[] = [
      { ...base, data: "2025-06-03" },
      { ...base, data: "2025-06-04", mm20: 10, macd_hist: -0.5 },
    ];
    expect(serieIndicador(itens, "mm20")).toEqual([{ time: "2025-06-04", value: 10 }]);
    expect(histogramaMacd(itens, "v", "r")).toEqual([{ time: "2025-06-04", value: -0.5, color: "r" }]);
  });
});

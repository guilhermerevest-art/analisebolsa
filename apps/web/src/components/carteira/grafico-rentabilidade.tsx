"use client";

import { ColorType, createChart, type IChartApi, LineSeries, type MouseEventParams, type Time } from "lightweight-charts";
import { useEffect, useMemo, useRef, useState } from "react";

import { classeVariacao, formatarData, formatarPct } from "@/lib/formato";
import type { RentabilidadeCarteira } from "@/lib/tipos-api";
import { useTemaEscuro } from "@/lib/use-tema-escuro";
import { cn } from "@/lib/utils";

// Paleta validada (scripts/validate_palette.js do dataviz) no claro e no escuro.
const SERIES = [
  { chave: "carteira", rotulo: "Carteira", claro: "#2563eb", escuro: "#3b82f6" },
  { chave: "cdi", rotulo: "CDI", claro: "#d97706", escuro: "#d97706" },
  { chave: "ibov", rotulo: "Ibovespa", claro: "#9333ea", escuro: "#a855f7" },
] as const;

type Chave = (typeof SERIES)[number]["chave"];
type Valores = { data: string } & Record<Chave, number | null>;

export function GraficoRentabilidade({ dados }: { dados: RentabilidadeCarteira }) {
  const escuro = useTemaEscuro();
  const container = useRef<HTMLDivElement>(null);
  const ultimo = useMemo<Valores | null>(() => {
    const p = dados.pontos.at(-1);
    return p ? { data: p.data, carteira: p.carteira, cdi: p.cdi, ibov: p.ibov } : null;
  }, [dados]);
  const [foco, setFoco] = useState<Valores | null>(null);

  useEffect(() => {
    if (!container.current || dados.pontos.length === 0) return;
    const texto = escuro ? "#d4d4d8" : "#3f3f46";
    const grade = escuro ? "#27272a" : "#f4f4f5";
    const chart: IChartApi = createChart(container.current, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: texto, fontFamily: "inherit" },
      grid: { vertLines: { visible: false }, horzLines: { color: grade } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
      handleScroll: false,
      handleScale: false,
      localization: {
        locale: "pt-BR",
        priceFormatter: (p: number) => `${p.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`,
      },
    });
    const porChave = new Map<Chave, ReturnType<IChartApi["addSeries"]>>();
    for (const s of SERIES) {
      const pontos = dados.pontos.filter((p) => p[s.chave] !== null).map((p) => ({ time: p.data as Time, value: p[s.chave] as number }));
      if (pontos.length === 0) continue;
      const serie = chart.addSeries(LineSeries, {
        color: escuro ? s.escuro : s.claro,
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: true,
        title: s.rotulo,
        crosshairMarkerRadius: 4,
      });
      serie.setData(pontos);
      porChave.set(s.chave, serie);
    }
    chart.timeScale().fitContent();

    const mover = (param: MouseEventParams) => {
      if (!param.time) return setFoco(null);
      const v = { data: String(param.time) } as Valores;
      for (const s of SERIES) {
        const serie = porChave.get(s.chave);
        const d = serie ? (param.seriesData.get(serie) as { value?: number } | undefined) : undefined;
        v[s.chave] = d?.value ?? null;
      }
      setFoco(v);
    };
    chart.subscribeCrosshairMove(mover);
    return () => {
      chart.unsubscribeCrosshairMove(mover);
      chart.remove();
    };
  }, [dados, escuro]);

  const mostrar = foco ?? ultimo;
  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1 text-sm" aria-live="polite">
        {SERIES.map((s) => (
          <span key={s.chave} className="flex items-center gap-2">
            <span aria-hidden className="inline-block h-0.5 w-4 rounded-full" style={{ backgroundColor: escuro ? s.escuro : s.claro }} />
            <span className="text-muted-foreground">{s.rotulo}</span>
            <span className={cn("font-medium tabular-nums", classeVariacao(mostrar?.[s.chave] ?? null))}>{formatarPct(mostrar?.[s.chave] ?? null)}</span>
          </span>
        ))}
        {mostrar && <span className="text-xs text-muted-foreground">até {formatarData(mostrar.data)}</span>}
      </div>
      <div ref={container} className="h-72 w-full" role="img" aria-label="Rentabilidade acumulada da carteira, do CDI e do Ibovespa no mesmo período" />
    </div>
  );
}

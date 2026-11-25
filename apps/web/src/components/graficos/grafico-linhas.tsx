"use client";

import { ColorType, createChart, type IChartApi, LineSeries, LineStyle, type MouseEventParams, type Time } from "lightweight-charts";
import { useEffect, useMemo, useRef, useState } from "react";

import { classeVariacao, formatarData, formatarPct, formatarPreco } from "@/lib/formato";
import { useTemaEscuro } from "@/lib/use-tema-escuro";
import { cn } from "@/lib/utils";

export type SerieLinha = { chave: string; rotulo: string; claro: string; escuro: string; tracejada?: boolean };
export type PontoLinhas = { data: string } & Record<string, number | null | string | undefined>;
type Valores = { data: string; v: Record<string, number | null> };

const brlCompacto = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", notation: "compact", maximumFractionDigits: 1 });
const FORMATOS = {
  pct: { eixo: (p: number) => `${p.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`, legenda: formatarPct, colorir: true },
  brl: { eixo: (p: number) => brlCompacto.format(p), legenda: formatarPreco, colorir: false },
} as const;

const valorDe = (p: PontoLinhas, chave: string) => (typeof p[chave] === "number" ? (p[chave] as number) : null);

/** Gráfico de linhas num eixo só, com legenda que acompanha o cursor e rótulos no eixo. */
export function GraficoLinhas({
  pontos,
  series,
  formato,
  rotuloAcessivel,
  altura = "h-72",
}: {
  pontos: PontoLinhas[];
  series: SerieLinha[];
  formato: keyof typeof FORMATOS;
  rotuloAcessivel: string;
  altura?: string;
}) {
  const escuro = useTemaEscuro();
  const container = useRef<HTMLDivElement>(null);
  const fmt = FORMATOS[formato];
  const visiveis = useMemo(() => series.filter((s) => pontos.some((p) => valorDe(p, s.chave) !== null)), [series, pontos]);
  const ultimo = useMemo<Valores | null>(() => {
    const p = pontos.at(-1);
    return p ? { data: p.data, v: Object.fromEntries(visiveis.map((s) => [s.chave, valorDe(p, s.chave)])) } : null;
  }, [pontos, visiveis]);
  const [foco, setFoco] = useState<Valores | null>(null);

  useEffect(() => {
    if (!container.current || pontos.length === 0) return;
    const chart: IChartApi = createChart(container.current, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: escuro ? "#d4d4d8" : "#3f3f46", fontFamily: "inherit" },
      grid: { vertLines: { visible: false }, horzLines: { color: escuro ? "#27272a" : "#f4f4f5" } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
      handleScroll: false,
      handleScale: false,
      localization: { locale: "pt-BR", priceFormatter: FORMATOS[formato].eixo },
    });
    const porChave = new Map<string, ReturnType<IChartApi["addSeries"]>>();
    for (const s of visiveis) {
      const dados = pontos.filter((p) => valorDe(p, s.chave) !== null).map((p) => ({ time: p.data as Time, value: valorDe(p, s.chave) as number }));
      const serie = chart.addSeries(LineSeries, {
        color: escuro ? s.escuro : s.claro,
        lineWidth: 2,
        lineStyle: s.tracejada ? LineStyle.Dashed : LineStyle.Solid,
        priceLineVisible: false,
        lastValueVisible: true,
        title: s.rotulo,
        crosshairMarkerRadius: 4,
      });
      serie.setData(dados);
      porChave.set(s.chave, serie);
    }
    chart.timeScale().fitContent();

    const mover = (param: MouseEventParams) => {
      if (!param.time) return setFoco(null);
      const v: Record<string, number | null> = {};
      for (const [chave, serie] of porChave) v[chave] = (param.seriesData.get(serie) as { value?: number } | undefined)?.value ?? null;
      setFoco({ data: String(param.time), v });
    };
    chart.subscribeCrosshairMove(mover);
    return () => {
      chart.unsubscribeCrosshairMove(mover);
      chart.remove();
    };
  }, [pontos, visiveis, escuro, formato]);

  const mostrar = foco ?? ultimo;
  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1 text-sm" aria-live="polite">
        {visiveis.map((s) => {
          const valor = mostrar?.v[s.chave] ?? null;
          return (
            <span key={s.chave} className="flex items-center gap-2">
              <span
                aria-hidden
                className={cn("inline-block w-4", s.tracejada ? "border-t-2 border-dashed" : "h-0.5 rounded-full")}
                style={s.tracejada ? { borderColor: escuro ? s.escuro : s.claro } : { backgroundColor: escuro ? s.escuro : s.claro }}
              />
              <span className="text-muted-foreground">{s.rotulo}</span>
              <span className={cn("font-medium tabular-nums", fmt.colorir && classeVariacao(valor))}>{fmt.legenda(valor)}</span>
            </span>
          );
        })}
        {mostrar && <span className="text-xs text-muted-foreground">em {formatarData(mostrar.data)}</span>}
      </div>
      <div ref={container} className={cn(altura, "w-full")} role="img" aria-label={rotuloAcessivel} />
    </div>
  );
}

"use client";

import { ColorType, createChart, createSeriesMarkers, LineSeries, type SeriesMarker, type Time } from "lightweight-charts";
import { useEffect, useRef } from "react";

import { useTemaEscuro } from "@/lib/use-tema-escuro";

type Ponto = { data: string; preco: number };
type Operacao = { entrada: string; saida?: string | null; motivo: "sinal" | "stop" | "aberta" };

// Preço em cinza para as marcas se destacarem: entrada em azul (abaixo), saída em âmbar (acima).
const CORES = {
  claro: { linha: "#71717a", entrada: "#2563eb", saida: "#d97706", texto: "#3f3f46", grade: "#f4f4f5" },
  escuro: { linha: "#a1a1aa", entrada: "#3b82f6", saida: "#d97706", texto: "#d4d4d8", grade: "#27272a" },
};
const MARCAS_COM_TEXTO = 40;

/** Preço ajustado do período com as entradas (▲) e saídas (▼) da estratégia. */
export function GraficoOperacoes({ pontos, operacoes }: { pontos: Ponto[]; operacoes: Operacao[] }) {
  const escuro = useTemaEscuro();
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current || pontos.length === 0) return;
    const cor = escuro ? CORES.escuro : CORES.claro;
    const chart = createChart(container.current, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: cor.texto, fontFamily: "inherit" },
      grid: { vertLines: { visible: false }, horzLines: { color: cor.grade } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
      handleScroll: { vertTouchDrag: false },
      localization: { locale: "pt-BR", priceFormatter: (p: number) => p.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) },
    });
    const serie = chart.addSeries(LineSeries, { color: cor.linha, lineWidth: 2, priceLineVisible: false, title: "Preço ajustado" });
    serie.setData(pontos.map((p) => ({ time: p.data as Time, value: p.preco })));

    const comTexto = operacoes.length * 2 <= MARCAS_COM_TEXTO;
    const marcas: SeriesMarker<Time>[] = [];
    for (const o of operacoes) {
      marcas.push({ time: o.entrada as Time, position: "belowBar", shape: "arrowUp", color: cor.entrada, text: comTexto ? "Entrada" : "" });
      if (o.saida) {
        marcas.push({ time: o.saida as Time, position: "aboveBar", shape: "arrowDown", color: cor.saida, text: comTexto ? (o.motivo === "stop" ? "Stop" : "Saída") : "" });
      }
    }
    marcas.sort((a, b) => String(a.time).localeCompare(String(b.time)));
    createSeriesMarkers(serie, marcas);
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [pontos, operacoes, escuro]);

  const cor = escuro ? CORES.escuro : CORES.claro;
  return (
    <div className="grid gap-2">
      <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span aria-hidden style={{ color: cor.entrada }}>▲</span> Entrada
        </span>
        <span className="flex items-center gap-1.5">
          <span aria-hidden style={{ color: cor.saida }}>▼</span> Saída (regra ou stop)
        </span>
      </div>
      <div
        ref={container}
        className="h-80 w-full"
        role="img"
        aria-label={`Preço ajustado do ativo com ${operacoes.length} entradas e as saídas da estratégia marcadas`}
      />
    </div>
  );
}

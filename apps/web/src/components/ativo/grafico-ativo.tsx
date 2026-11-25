"use client";

import {
  CandlestickSeries,
  ColorType,
  createChart,
  HistogramSeries,
  type IChartApi,
  LineSeries,
} from "lightweight-charts";
import { useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  histogramaMacd,
  INTERVALOS,
  type Intervalo,
  inicioDoPeriodo,
  type Periodo,
  PERIODOS,
  paraCandles,
  paraVolume,
  serieIndicador,
} from "@/lib/grafico";
import type { Cotacoes, Indicadores } from "@/lib/tipos-api";
import { cn } from "@/lib/utils";

const ALTA = "#16a34a";
const BAIXA = "#dc2626";
const OVERLAYS = [
  { chave: "mm20", rotulo: "MM20", cor: "#2563eb" },
  { chave: "mm50", rotulo: "MM50", cor: "#f59e0b" },
  { chave: "mm200", rotulo: "MM200", cor: "#a855f7" },
  { chave: "bb", rotulo: "Bollinger", cor: "#64748b" },
] as const;
type ChaveOverlay = (typeof OVERLAYS)[number]["chave"];

type Dados = { cotacoes: Cotacoes; indicadores: Indicadores | null };

function useTemaEscuro(): boolean {
  const [escuro, setEscuro] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    setEscuro(mq.matches);
    const ouvir = (e: MediaQueryListEvent) => setEscuro(e.matches);
    mq.addEventListener("change", ouvir);
    return () => mq.removeEventListener("change", ouvir);
  }, []);
  return escuro;
}

function Alternador<T extends string>({
  opcoes,
  valor,
  onChange,
  rotulo,
}: {
  opcoes: { valor: T; rotulo: string; desabilitado?: boolean }[];
  valor: T;
  onChange: (v: T) => void;
  rotulo: string;
}) {
  return (
    <div role="group" aria-label={rotulo} className="inline-flex rounded-md border p-0.5">
      {opcoes.map((o) => (
        <button
          key={o.valor}
          type="button"
          disabled={o.desabilitado}
          aria-pressed={valor === o.valor}
          onClick={() => onChange(o.valor)}
          className={cn(
            "rounded px-2.5 py-1 text-xs font-medium transition-colors disabled:opacity-40",
            valor === o.valor ? "bg-primary text-primary-foreground" : "hover:bg-accent",
          )}
        >
          {o.rotulo}
        </button>
      ))}
    </div>
  );
}

export function GraficoAtivo({ ticker }: { ticker: string }) {
  const container = useRef<HTMLDivElement>(null);
  const [periodo, setPeriodo] = useState<Periodo>("1A");
  const [intervalo, setIntervalo] = useState<Intervalo>("D");
  const [overlays, setOverlays] = useState<Set<ChaveOverlay>>(new Set(["mm20", "mm50"]));
  const [osciladores, setOsciladores] = useState({ rsi: true, macd: false });
  const [dados, setDados] = useState<Dados | null>(null);
  const [erro, setErro] = useState(false);
  const escuro = useTemaEscuro();

  // Indicadores são pré-calculados no diário; nos intervalos S e M ficam desligados.
  const diario = intervalo === "D";

  useEffect(() => {
    const controle = new AbortController();
    const inicio = inicioDoPeriodo(periodo);
    const api = INTERVALOS.find((i) => i.valor === intervalo)!.api;
    setErro(false);
    Promise.all([
      fetch(`/api/ativos/${ticker}/cotacoes?inicio=${inicio}&periodo=${api}`, { signal: controle.signal }).then(
        (r) => (r.ok ? (r.json() as Promise<Cotacoes>) : Promise.reject(r.status)),
      ),
      diario
        ? fetch(`/api/ativos/${ticker}/indicadores?inicio=${inicio}`, { signal: controle.signal }).then((r) =>
            r.ok ? (r.json() as Promise<Indicadores>) : null,
          )
        : Promise.resolve(null),
    ])
      .then(([cotacoes, indicadores]) => setDados({ cotacoes, indicadores }))
      .catch((e) => {
        if (!controle.signal.aborted) {
          console.error("falha ao carregar o gráfico", e);
          setErro(true);
        }
      });
    return () => controle.abort();
  }, [ticker, periodo, intervalo, diario]);

  const series = useMemo(() => {
    if (!dados) return null;
    const ind = dados.indicadores?.itens ?? [];
    return {
      candles: paraCandles(dados.cotacoes.candles),
      volume: paraVolume(dados.cotacoes.candles, `${ALTA}66`, `${BAIXA}66`),
      ind,
    };
  }, [dados]);

  useEffect(() => {
    if (!container.current || !series) return;
    const texto = escuro ? "#d4d4d8" : "#3f3f46";
    const grade = escuro ? "#27272a" : "#f4f4f5";
    const chart: IChartApi = createChart(container.current, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: texto,
        fontFamily: "inherit",
        panes: { separatorColor: grade },
      },
      grid: { vertLines: { color: grade }, horzLines: { color: grade } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
      localization: {
        locale: "pt-BR",
        priceFormatter: (p: number) => p.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
      },
    });

    const candles = chart.addSeries(CandlestickSeries, {
      upColor: ALTA,
      downColor: BAIXA,
      borderVisible: false,
      wickUpColor: ALTA,
      wickDownColor: BAIXA,
    });
    candles.setData(series.candles);

    const volume = chart.addSeries(HistogramSeries, {
      priceScaleId: "volume",
      priceFormat: { type: "volume" },
      lastValueVisible: false,
      priceLineVisible: false,
    });
    volume.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
    volume.setData(series.volume);

    if (diario) {
      const linha = { lineWidth: 1 as const, lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false };
      for (const o of OVERLAYS) {
        if (!overlays.has(o.chave)) continue;
        if (o.chave === "bb") {
          chart.addSeries(LineSeries, { ...linha, color: o.cor, lineStyle: 2 }).setData(serieIndicador(series.ind, "bb_superior"));
          chart.addSeries(LineSeries, { ...linha, color: o.cor, lineStyle: 2 }).setData(serieIndicador(series.ind, "bb_inferior"));
        } else {
          chart.addSeries(LineSeries, { ...linha, color: o.cor }).setData(serieIndicador(series.ind, o.chave));
        }
      }
      let pane = 1;
      if (osciladores.rsi) {
        const rsi = chart.addSeries(LineSeries, { ...linha, color: "#7c3aed", lastValueVisible: true }, pane);
        rsi.setData(serieIndicador(series.ind, "rsi14"));
        rsi.createPriceLine({ price: 70, color: BAIXA, lineStyle: 2, lineWidth: 1, axisLabelVisible: false, title: "" });
        rsi.createPriceLine({ price: 30, color: ALTA, lineStyle: 2, lineWidth: 1, axisLabelVisible: false, title: "" });
        pane++;
      }
      if (osciladores.macd) {
        chart.addSeries(HistogramSeries, { lastValueVisible: false, priceLineVisible: false }, pane).setData(
          histogramaMacd(series.ind, `${ALTA}99`, `${BAIXA}99`),
        );
        chart.addSeries(LineSeries, { ...linha, color: "#2563eb" }, pane).setData(serieIndicador(series.ind, "macd"));
        chart.addSeries(LineSeries, { ...linha, color: "#f59e0b" }, pane).setData(serieIndicador(series.ind, "macd_sinal"));
      }
      const panes = chart.panes();
      panes.slice(1).forEach((p) => p.setHeight(110));
    }

    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [series, overlays, osciladores, diario, escuro]);

  const alternarOverlay = (chave: ChaveOverlay) =>
    setOverlays((atual) => {
      const novo = new Set(atual);
      if (novo.has(chave)) novo.delete(chave);
      else novo.add(chave);
      return novo;
    });

  const altura = 420 + (diario ? (osciladores.rsi ? 110 : 0) + (osciladores.macd ? 110 : 0) : 0);

  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Alternador
          rotulo="Período"
          opcoes={PERIODOS.map((p) => ({ valor: p, rotulo: p === "MAX" ? "Máx" : p }))}
          valor={periodo}
          onChange={setPeriodo}
        />
        <Alternador
          rotulo="Intervalo"
          opcoes={INTERVALOS.map((i) => ({ valor: i.valor, rotulo: i.valor, desabilitado: periodo === "1M" && i.valor === "M" }))}
          valor={intervalo}
          onChange={setIntervalo}
        />
        <div className="flex flex-wrap gap-1" role="group" aria-label="Indicadores">
          {OVERLAYS.map((o) => (
            <Button
              key={o.chave}
              type="button"
              size="sm"
              variant={diario && overlays.has(o.chave) ? "default" : "outline"}
              disabled={!diario}
              aria-pressed={overlays.has(o.chave)}
              onClick={() => alternarOverlay(o.chave)}
            >
              <span className="size-2 rounded-full" style={{ background: o.cor }} aria-hidden />
              {o.rotulo}
            </Button>
          ))}
          {(["rsi", "macd"] as const).map((k) => (
            <Button
              key={k}
              type="button"
              size="sm"
              variant={diario && osciladores[k] ? "default" : "outline"}
              disabled={!diario}
              aria-pressed={osciladores[k]}
              onClick={() => setOsciladores((o) => ({ ...o, [k]: !o[k] }))}
            >
              {k.toUpperCase()}
            </Button>
          ))}
        </div>
      </div>
      {!diario && <p className="text-xs text-muted-foreground">Os indicadores aparecem no intervalo diário.</p>}
      <div className="relative w-full" style={{ height: altura }}>
        <div ref={container} className="absolute inset-0" />
        {!dados && !erro && <div className="absolute inset-0 animate-pulse rounded-md bg-muted" aria-label="Carregando gráfico" />}
        {erro && (
          <p className="absolute inset-0 grid place-items-center text-sm text-muted-foreground">
            Não foi possível carregar o gráfico.
          </p>
        )}
        {dados && dados.cotacoes.candles.length === 0 && (
          <p className="absolute inset-0 grid place-items-center text-sm text-muted-foreground">Sem cotações no período.</p>
        )}
      </div>
    </div>
  );
}


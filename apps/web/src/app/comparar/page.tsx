import { Lightbulb } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { Termo } from "@/components/dica";
import { GraficoLinhasCliente } from "@/components/graficos/grafico-linhas-cliente";
import type { SerieLinha } from "@/components/graficos/grafico-linhas";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { lerComparacao } from "@/lib/dados";
import { classeVariacao, formatarCompacto, formatarData, formatarNumero, formatarPct, formatarPreco } from "@/lib/formato";
import type { ChaveGlossario } from "@/lib/glossario";
import { inicioDoPeriodo, PERIODOS, type Periodo } from "@/lib/mercado";
import type { Comparacao } from "@/lib/tipos-api";
import { cn } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Comparar ativos",
  description: "Compare de 2 a 4 ativos da B3 lado a lado: desempenho com proventos, risco, fundamentos e liquidez.",
};

type Props = { searchParams: Promise<{ t?: string; periodo?: string }> };
type Ativo = Comparacao["ativos"][number];

// Mesma paleta validada dos outros gráficos, uma cor por ativo.
const CORES = [
  { claro: "#2f6bff", escuro: "#5a88ff" },
  { claro: "#d97706", escuro: "#d97706" },
  { claro: "#9333ea", escuro: "#a855f7" },
  { claro: "#0e9f8e", escuro: "#2dd4bf" },
];
const EXEMPLOS = [
  ["PETR4", "VALE3"],
  ["ITUB4", "BBAS3", "BBDC4"],
  ["HGLG11", "XPLG11", "BTLG11"],
  ["BOVA11", "IVVB11"],
];

const pctSimples = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${formatarNumero(v)}%`);
const NOMES_TENDENCIA = { alta: "Alta", baixa: "Baixa", lateral: "Lateral" } as const;

const LINHAS: { rotulo: string; termo?: ChaveGlossario; valor: (a: Ativo) => React.ReactNode }[] = [
  { rotulo: "Preço", valor: (a) => formatarPreco(a.preco) },
  { rotulo: "Dia", valor: (a) => <Var v={a.var_1d} /> },
  { rotulo: "No ano", valor: (a) => <Var v={a.var_ano} /> },
  { rotulo: "12 meses", termo: "retorno_total", valor: (a) => <Var v={a.var_12m} /> },
  { rotulo: "Volatilidade (12m)", termo: "volatilidade", valor: (a) => pctSimples(a.volatilidade_12m) },
  { rotulo: "Queda máxima (12m)", termo: "queda_maxima", valor: (a) => <Var v={a.drawdown_12m} /> },
  { rotulo: "Tendência", termo: "tendencia", valor: (a) => (a.tendencia ? NOMES_TENDENCIA[a.tendencia] : "—") },
  { rotulo: "RSI", termo: "rsi", valor: (a) => formatarNumero(a.rsi14, 0) },
  { rotulo: "Dividend yield", termo: "dy", valor: (a) => pctSimples(a.dy_12m) },
  { rotulo: "P/L", termo: "pl", valor: (a) => formatarNumero(a.pl, 1) },
  { rotulo: "P/VP", termo: "pvp", valor: (a) => formatarNumero(a.pvp, 2) },
  { rotulo: "ROE", termo: "roe", valor: (a) => pctSimples(a.roe) },
  { rotulo: "Margem líquida", termo: "margem_liquida", valor: (a) => pctSimples(a.margem_liquida) },
  { rotulo: "Liquidez diária", termo: "liquidez", valor: (a) => (a.volume_financeiro_20d === null ? "—" : `R$ ${formatarCompacto(a.volume_financeiro_20d)}`) },
];

function Var({ v }: { v: number | null | undefined }) {
  return <span className={classeVariacao(v ?? null)}>{formatarPct(v ?? null)}</span>;
}

function lerTickers(t: string | undefined): string[] {
  return [...new Set((t ?? "").toUpperCase().split(/[\s,;]+/).filter((x) => /^[A-Z0-9]{4,6}$/.test(x)))].slice(0, 4);
}

export default async function Comparar({ searchParams }: Props) {
  const params = await searchParams;
  const tickers = lerTickers(params.t);
  const periodo: Periodo = params.periodo && params.periodo in PERIODOS ? (params.periodo as Periodo) : "1a";
  const resposta = tickers.length >= 2 ? await lerComparacao(tickers, inicioDoPeriodo(periodo)) : null;
  const dados = resposta && "dados" in resposta ? resposta.dados : null;
  const erro = resposta && "erro" in resposta ? resposta.erro : null;

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-8">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Comparar ativos</h1>
        <p className="mt-2 max-w-2xl text-muted-foreground">
          Coloque de 2 a 4 ativos lado a lado: quanto cada um rendeu com os proventos, quanto oscilou e como estão os fundamentos.
        </p>
      </div>

      <form method="get" action="/comparar" className="grid gap-3 rounded-xl border bg-card p-4 sm:grid-cols-[1fr_auto] sm:items-end">
        <input type="hidden" name="periodo" value={periodo} />
        <div className="grid gap-2">
          <Label htmlFor="t">Ativos, separados por vírgula</Label>
          <Input id="t" name="t" defaultValue={tickers.join(", ")} placeholder="PETR4, VALE3, ITUB4…" autoCapitalize="characters" autoComplete="off" spellCheck={false} />
        </div>
        <Button type="submit">Comparar</Button>
        <p className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground sm:col-span-2">
          Exemplos:
          {EXEMPLOS.map((e) => (
            <Link key={e.join()} href={`/comparar?t=${e.join(",")}&periodo=${periodo}`} className="rounded-md border bg-card px-2 py-0.5 text-xs font-medium text-foreground hover:border-azul hover:text-azul">
              {e.join(" × ")}
            </Link>
          ))}
        </p>
      </form>

      {tickers.length === 1 && <p className="text-sm text-muted-foreground">Escolha pelo menos mais um ativo para comparar.</p>}
      {erro && <p role="alert" className="text-sm text-destructive">{erro.charAt(0).toUpperCase() + erro.slice(1)}.</p>}
      {dados && <Resultado dados={dados} periodo={periodo} tickers={tickers} />}
    </div>
  );
}

function Resultado({ dados, periodo, tickers }: { dados: Comparacao; periodo: Periodo; tickers: string[] }) {
  // Junta as séries por data para o gráfico: { data, PETR4: 104.2, VALE3: 97.1 }.
  const porData = new Map<string, Record<string, number | string | null>>();
  for (const s of dados.series) {
    for (const p of s.pontos) {
      const linha = porData.get(p.data) ?? { data: p.data };
      linha[s.ticker] = p.valor;
      porData.set(p.data, linha);
    }
  }
  const pontos = [...porData.values()].sort((a, b) => String(a.data).localeCompare(String(b.data))) as { data: string }[];
  const series: SerieLinha[] = dados.series.map((s, i) => ({ chave: s.ticker, rotulo: s.ticker, ...CORES[i % CORES.length] }));
  const retornos = dados.series
    .map((s) => ({ ticker: s.ticker, r: s.pontos.length ? s.pontos.at(-1)!.valor / 100 - 1 : null }))
    .filter((x): x is { ticker: string; r: number } => x.r !== null)
    .sort((a, b) => b.r - a.r);

  return (
    <>
      <section aria-labelledby="titulo-desempenho" className="grid gap-4 rounded-xl border bg-card p-5">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 id="titulo-desempenho" className="text-xl font-semibold">
              Desempenho com proventos (base 100)
            </h2>
            {dados.inicio && <p className="text-sm text-muted-foreground">Todos começam em 100 em {formatarData(dados.inicio)}.</p>}
          </div>
          <nav aria-label="Período" className="flex gap-1">
            {(Object.keys(PERIODOS) as Periodo[]).map((p) => (
              <Button key={p} asChild size="sm" variant={p === periodo ? "default" : "outline"}>
                <Link href={`/comparar?t=${tickers.join(",")}&periodo=${p}`} aria-current={p === periodo ? "true" : undefined}>
                  {PERIODOS[p].rotulo}
                </Link>
              </Button>
            ))}
          </nav>
        </div>
        {pontos.length > 1 ? (
          <GraficoLinhasCliente pontos={pontos} series={series} formato="num" rotuloAcessivel={`Desempenho de ${tickers.join(", ")} com base 100`} />
        ) : (
          <p className="text-sm text-muted-foreground">Não há cotações em comum nesse período.</p>
        )}
        {retornos.length > 1 && (
          <aside className="grid gap-1 rounded-xl border-l-4 border-l-azul bg-accent/60 p-4 text-sm leading-relaxed">
            <p className="flex items-center gap-2 font-semibold">
              <Lightbulb aria-hidden className="size-4 text-azul" />
              Como ler
            </p>
            <p>
              Do maior para o menor retorno no período, com os proventos reinvestidos:{" "}
              {retornos.map((x, i) => (
                <span key={x.ticker}>
                  {i > 0 && ", "}
                  <span className="font-medium">{x.ticker}</span> (<Var v={x.r * 100} />)
                </span>
              ))}
              . Cada R$ 100 aplicados no início valeriam R$ {formatarNumero(100 * (1 + retornos[0].r), 0)} em {retornos[0].ticker} e R${" "}
              {formatarNumero(100 * (1 + retornos.at(-1)!.r), 0)} em {retornos.at(-1)!.ticker}. É o passado: não indica o que vem pela frente.
            </p>
          </aside>
        )}
      </section>

      <section aria-labelledby="titulo-metricas" className="grid gap-3">
        <h2 id="titulo-metricas" className="text-xl font-semibold">
          Lado a lado
        </h2>
        <div className="overflow-x-auto rounded-xl border bg-card">
          <table className="w-full text-sm">
            <caption className="sr-only">Métricas do último pregão de cada ativo</caption>
            <thead className="border-b">
              <tr>
                <th scope="col" className="px-4 py-3 text-left font-medium text-muted-foreground">
                  Métrica
                </th>
                {dados.ativos.map((a, i) => (
                  <th key={a.ticker} scope="col" className="px-4 py-3 text-right">
                    <Link href={`/ativo/${a.ticker}`} className="inline-flex items-center gap-1.5 font-semibold hover:text-azul">
                      <span aria-hidden className="size-2 rounded-full" style={{ background: CORES[i % CORES.length].claro }} />
                      {a.ticker}
                    </Link>
                    <span className="block text-xs font-normal text-muted-foreground">{a.nome}</span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y">
              {LINHAS.map((l) => (
                <tr key={l.rotulo}>
                  <th scope="row" className="whitespace-nowrap px-4 py-2 text-left font-normal text-muted-foreground">
                    {l.termo ? <Termo termo={l.termo}>{l.rotulo}</Termo> : l.rotulo}
                  </th>
                  {dados.ativos.map((a) => (
                    <td key={a.ticker} className={cn("whitespace-nowrap px-4 py-2 text-right tabular-nums")}>
                      {a.preco === null || a.preco === undefined ? <span className="text-muted-foreground">—</span> : l.valor(a)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-muted-foreground">
          Métricas do último pregão. Ativos com pouca negociação podem não ter todas calculadas. Conteúdo educacional, não é recomendação de
          investimento.
        </p>
      </section>
    </>
  );
}

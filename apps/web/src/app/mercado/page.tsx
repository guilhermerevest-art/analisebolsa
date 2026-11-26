import type { Metadata } from "next";
import Link from "next/link";

import { Termo } from "@/components/dica";
import { GraficoLinhasCliente } from "@/components/graficos/grafico-linhas-cliente";
import type { SerieLinha } from "@/components/graficos/grafico-linhas";
import { Miniatura } from "@/components/mercado/miniatura";
import { Button } from "@/components/ui/button";
import { lerIndicadores, lerSerieIndice } from "@/lib/dados";
import { classeVariacao, formatarData, formatarPct } from "@/lib/formato";
import { GLOSSARIO } from "@/lib/glossario";
import { formatarIndicador, inicioDoPeriodo, PERIODOS, TERMO_INDICADOR, type Periodo } from "@/lib/mercado";
import type { IndicadorMercado } from "@/lib/tipos-api";
import { cn } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Mercado",
  description: "Ibovespa, IFIX, Small Caps, Dividendos, dólar, euro, S&P 500 e bitcoin: valores, variações e gráficos históricos.",
};
export const revalidate = 300;

type Props = { searchParams: Promise<{ serie?: string; periodo?: string }> };

function Variacao({ rotulo, v }: { rotulo: string; v: number | null | undefined }) {
  return (
    <div className="grid">
      <dt className="text-xs text-muted-foreground">{rotulo}</dt>
      <dd className={cn("text-sm font-medium tabular-nums", classeVariacao(v ?? null))}>{formatarPct(v ?? null)}</dd>
    </div>
  );
}

function Cartao({ i, ativo }: { i: IndicadorMercado; ativo: boolean }) {
  const termo = TERMO_INDICADOR[i.serie];
  return (
    <li className={cn("grid gap-3 rounded-xl border bg-card p-4", ativo && "border-azul ring-1 ring-azul")}>
      <div className="flex items-start justify-between gap-2">
        <h2 className="text-sm font-medium text-muted-foreground">{termo ? <Termo termo={termo}>{i.nome}</Termo> : i.nome}</h2>
        <span className="text-xs text-muted-foreground">{formatarData(i.data)}</span>
      </div>
      <p className="font-display text-2xl font-semibold tracking-tight tabular-nums">{formatarIndicador(i.valor, i.unidade)}</p>
      <dl className="grid grid-cols-3 gap-2">
        <Variacao rotulo="Dia" v={i.var_dia} />
        <Variacao rotulo="Ano" v={i.var_ano} />
        <Variacao rotulo="12 meses" v={i.var_12m} />
      </dl>
      <Miniatura valores={i.pontos.map((p) => p.valor)} />
      <Button asChild variant={ativo ? "default" : "outline"} size="sm" className="w-full">
        <Link href={`/mercado?serie=${i.serie}#grafico`} aria-current={ativo ? "true" : undefined}>
          {ativo ? "No gráfico abaixo" : "Ver gráfico"}
        </Link>
      </Button>
    </li>
  );
}

/** Um ponto por semana quando a série é longa (o gráfico fica leve e o desenho não muda). */
function semanal<T extends { data: string }>(pontos: T[]): T[] {
  if (pontos.length <= 1500) return pontos;
  const porSemana = new Map<string, T>();
  for (const p of pontos) {
    const d = new Date(`${p.data}T12:00:00Z`);
    const segunda = new Date(d);
    segunda.setUTCDate(d.getUTCDate() - ((d.getUTCDay() + 6) % 7));
    porSemana.set(segunda.toISOString().slice(0, 10), p);
  }
  return [...porSemana.values()];
}

export default async function Mercado({ searchParams }: Props) {
  const params = await searchParams;
  const dados = await lerIndicadores();
  const itens = dados?.itens ?? [];
  const escolhido = itens.find((i) => i.serie === params.serie) ?? itens[0];
  const periodo: Periodo = params.periodo && params.periodo in PERIODOS ? (params.periodo as Periodo) : "5a";
  const serie = escolhido ? await lerSerieIndice(escolhido.serie, inicioDoPeriodo(periodo)) : null;
  const pontos = semanal(serie?.pontos ?? []);
  const primeiro = pontos[0];
  const ultimo = pontos.at(-1);
  const linha: SerieLinha[] = escolhido ? [{ chave: "valor", rotulo: escolhido.nome, claro: "#1f51ff", escuro: "#5b87ff" }] : [];

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-10">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Mercado</h1>
        <p className="mt-2 max-w-2xl text-muted-foreground">
          Os índices da bolsa, as moedas e as referências de fora, atualizados no fim de cada pregão. O ícone de interrogação ao lado de cada nome
          explica o que ele mede.
        </p>
      </div>

      {itens.length === 0 ? (
        <p role="alert" className="text-sm text-destructive">
          Não foi possível carregar os indicadores agora. Tente de novo em instantes.
        </p>
      ) : (
        <>
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {itens.map((i) => (
              <Cartao key={i.serie} i={i} ativo={i.serie === escolhido?.serie} />
            ))}
          </ul>

          {escolhido && (
            <section id="grafico" aria-labelledby="titulo-grafico" className="grid scroll-mt-24 gap-4 rounded-xl border bg-card p-5">
              <div className="flex flex-wrap items-end justify-between gap-3">
                <div>
                  <h2 id="titulo-grafico" className="text-xl font-semibold">
                    {escolhido.nome}
                  </h2>
                  {TERMO_INDICADOR[escolhido.serie] && (
                    <p className="mt-1 max-w-2xl text-sm text-muted-foreground">{GLOSSARIO[TERMO_INDICADOR[escolhido.serie]].curto}</p>
                  )}
                </div>
                <nav aria-label="Período" className="flex gap-1">
                  {(Object.keys(PERIODOS) as Periodo[]).map((p) => (
                    <Button key={p} asChild size="sm" variant={p === periodo ? "default" : "outline"}>
                      <Link href={`/mercado?serie=${escolhido.serie}&periodo=${p}#grafico`} aria-current={p === periodo ? "true" : undefined}>
                        {PERIODOS[p].rotulo}
                      </Link>
                    </Button>
                  ))}
                </nav>
              </div>
              {pontos.length > 1 ? (
                <>
                  <GraficoLinhasCliente
                    pontos={pontos}
                    series={linha}
                    formato={escolhido.unidade === "reais" ? "brl" : "num"}
                    rotuloAcessivel={`Evolução de ${escolhido.nome} em ${PERIODOS[periodo].rotulo.toLowerCase()}`}
                  />
                  {primeiro && ultimo && (
                    <p className="text-sm">
                      De {formatarData(primeiro.data)} a {formatarData(ultimo.data)}, foi de{" "}
                      <span className="font-medium tabular-nums">{formatarIndicador(primeiro.valor, escolhido.unidade)}</span> para{" "}
                      <span className="font-medium tabular-nums">{formatarIndicador(ultimo.valor, escolhido.unidade)}</span> (
                      <span className={cn("font-medium tabular-nums", classeVariacao(ultimo.valor / primeiro.valor - 1))}>
                        {formatarPct((ultimo.valor / primeiro.valor - 1) * 100)}
                      </span>
                      ).
                    </p>
                  )}
                </>
              ) : (
                <p className="text-sm text-muted-foreground">Ainda não há histórico para este período.</p>
              )}
            </section>
          )}

          <p className="text-xs text-muted-foreground">
            Fontes: Banco Central (dólar e euro pela PTAX), B3 (IFIX, Small Caps e Dividendos) e Yahoo Finance (Ibovespa, S&amp;P 500 e bitcoin). Os
            índices da B3 saem no dia útil seguinte. Conteúdo educacional, não é recomendação de investimento.
          </p>
        </>
      )}
    </div>
  );
}

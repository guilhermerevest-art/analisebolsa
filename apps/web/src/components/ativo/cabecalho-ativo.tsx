"use client";

import { EstrelaWatchlist } from "@/components/ativo/estrela-watchlist";
import { NumberTicker } from "@/components/magic/number-ticker";
import { classeVariacao, formatarData, formatarPct, formatarPreco, NOMES_TIPO } from "@/lib/formato";
import type { AtivoDetalhe } from "@/lib/tipos-api";
import { cn } from "@/lib/utils";

const fmt = (n: number) => formatarPreco(n);

export function CabecalhoAtivo({ ativo }: { ativo: AtivoDetalhe }) {
  const u = ativo.ultima_cotacao;
  const v = ativo.variacoes;
  return (
    <header className="flex flex-wrap items-end justify-between gap-6">
      <div className="flex items-center gap-4">
        {ativo.logo_url && (
          // eslint-disable-next-line @next/next/no-img-element -- logos externos em SVG
          <img src={ativo.logo_url} alt="" width={48} height={48} className="size-12 rounded-lg border bg-white object-contain p-1" />
        )}
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            {ativo.ticker} <span className="text-base font-normal text-muted-foreground">{ativo.nome}</span>
          </h1>
          <p className="text-sm text-muted-foreground">
            {NOMES_TIPO[ativo.tipo]}
            {ativo.setor && ` · ${ativo.setor}`}
            {ativo.segmento && ` · ${ativo.segmento}`}
          </p>
          <div className="mt-2">
            <EstrelaWatchlist ticker={ativo.ticker} />
          </div>
        </div>
      </div>
      {u && (
        <div className="sm:text-right">
          <NumberTicker valor={Number(u.fechamento)} formatar={fmt} className="font-display text-3xl font-semibold tracking-tight" />
          <dl className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm sm:justify-end">
            {(
              [
                ["Dia", v.dia],
                ["12 meses", v.doze_meses],
                ["No ano", v.ano],
              ] as const
            ).map(([rotulo, valor]) => (
              <div key={rotulo} className="flex gap-1">
                <dt className="text-muted-foreground">{rotulo}</dt>
                <dd className={cn("font-medium tabular-nums", classeVariacao(valor))}>{formatarPct(valor)}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-1 text-xs text-muted-foreground">Fechamento de {formatarData(u.data)}</p>
        </div>
      )}
    </header>
  );
}

import Link from "next/link";

import { Miniatura } from "@/components/mercado/miniatura";
import { classeVariacao, formatarPct } from "@/lib/formato";
import { formatarIndicador } from "@/lib/mercado";
import type { IndicadorMercado } from "@/lib/tipos-api";
import { cn } from "@/lib/utils";

/** Faixa da landing: os indicadores de mercado com o valor, a variação do dia e 12 meses em miniatura. */
export function FaixaMercado({ itens }: { itens: IndicadorMercado[] }) {
  if (itens.length === 0) return null;
  return (
    <section aria-labelledby="titulo-mercado" className="grid gap-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <h2 id="titulo-mercado" className="text-3xl font-semibold tracking-tight">
          Mercado hoje
        </h2>
        <Link href="/mercado" className="text-sm font-medium text-azul underline-offset-2 hover:underline">
          Ver gráficos e explicações
        </Link>
      </div>
      <ul className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {itens.map((i) => (
          <li key={i.serie}>
            <Link
              href={`/mercado?serie=${i.serie}`}
              className="grid gap-1 rounded-xl border bg-card p-4 transition-colors hover:border-azul focus-visible:border-azul"
            >
              <span className="text-sm text-muted-foreground">{i.nome}</span>
              <span className="font-display text-xl font-semibold tracking-tight tabular-nums">{formatarIndicador(i.valor, i.unidade)}</span>
              <span className="flex items-baseline justify-between gap-2 text-xs">
                <span className={cn("font-medium tabular-nums", classeVariacao(i.var_dia ?? null))}>{formatarPct(i.var_dia ?? null)} no dia</span>
                <span className={cn("tabular-nums", classeVariacao(i.var_12m ?? null))}>{formatarPct(i.var_12m ?? null)} em 12m</span>
              </span>
              <Miniatura valores={i.pontos.map((p) => p.valor)} className="mt-1" />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

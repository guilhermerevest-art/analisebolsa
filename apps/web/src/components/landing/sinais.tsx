import Link from "next/link";

import { formatarData, formatarNumero } from "@/lib/formato";
import { PRESETS, urlPreset } from "@/lib/screener";
import type { SinaisDoDia } from "@/lib/tipos-api";
import { cn } from "@/lib/utils";

const COR_TOM = { positivo: "bg-positivo", atencao: "bg-amber-500", neutro: "bg-muted-foreground" } as const;

// Sinais com um filtro pronto parecido no screener.
const preset = (id: string) => urlPreset(PRESETS.find((p) => p.id === id)!);
const NO_SCREENER: Record<string, string> = { maxima_52s: preset("maxima-52s"), minima_52s: preset("minima-52s") };

export function SinaisDeHoje({ dados }: { dados: SinaisDoDia }) {
  if (!dados.data || dados.sinais.length === 0) return null;
  return (
    <section aria-labelledby="sinais" className="grid gap-6">
      <div>
        <h2 id="sinais" className="text-2xl font-semibold tracking-tight">
          Sinais de hoje
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          O que os indicadores técnicos mostraram no pregão de {formatarData(dados.data)}, entre os ativos com liquidez para a análise. São
          descrições dos dados, não indicações de compra ou venda.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {dados.sinais.map((s) => (
          <div key={s.codigo} className="grid content-start gap-3 rounded-xl border bg-card p-5">
            <p className="flex items-start gap-2">
              <span className={cn("mt-2 size-2 shrink-0 rounded-full", COR_TOM[s.tom])} aria-hidden />
              <span>
                <span className="text-2xl font-semibold tabular-nums">{formatarNumero(s.total, 0)}</span>{" "}
                <span className="text-sm text-muted-foreground">
                  {s.total === 1 ? "ativo" : "ativos"} {s.frase}
                </span>
              </span>
            </p>
            <div className="flex flex-wrap gap-1.5">
              {s.exemplos.map((e) => (
                <Link key={e.ticker} href={`/ativo/${e.ticker}`} title={e.nome} className="rounded-md border px-2 py-0.5 text-xs font-medium hover:bg-muted">
                  {e.ticker}
                </Link>
              ))}
              {NO_SCREENER[s.codigo] && (
                <Link href={NO_SCREENER[s.codigo]} className="px-1 py-0.5 text-xs text-muted-foreground underline-offset-2 hover:underline">
                  ver no screener
                </Link>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

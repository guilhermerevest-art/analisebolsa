import { formatarNumero, formatarPreco } from "@/lib/formato";
import type { FatiaAlocacao } from "@/lib/tipos-api";

/** Barras horizontais de alocação, com o percentual escrito ao lado. */
export function BarrasAlocacao({ titulo, fatias }: { titulo: string; fatias: FatiaAlocacao[] }) {
  return (
    <section aria-label={`Alocação por ${titulo.toLowerCase()}`} className="grid content-start gap-3">
      <h3 className="text-sm font-medium">{titulo}</h3>
      {fatias.length === 0 ? (
        <p className="text-sm text-muted-foreground">—</p>
      ) : (
        <ul className="grid gap-2">
          {fatias.map((f) => (
            <li key={f.chave} className="grid gap-1 text-sm">
              <div className="flex items-baseline justify-between gap-2">
                <span className="truncate">{f.chave}</span>
                <span className="shrink-0 tabular-nums text-muted-foreground" title={formatarPreco(f.valor)}>
                  {formatarNumero(f.percentual, 1)}%
                </span>
              </div>
              <div className="h-2 rounded-full bg-muted" aria-hidden>
                <div className="h-2 rounded-full bg-azul" style={{ width: `${Math.max(f.percentual, 1)}%` }} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

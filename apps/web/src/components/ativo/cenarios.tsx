import { ArrowDownRight, ArrowRight, ArrowUpRight } from "lucide-react";

import { formatarData, formatarNumero, formatarPreco } from "@/lib/formato";
import type { CenarioPreco, CenariosAtivo } from "@/lib/tipos-api";
import { cn } from "@/lib/utils";

const ICONE = { alta: ArrowUpRight, lateral: ArrowRight, baixa: ArrowDownRight } as const;
const COR = { alta: "text-positivo", lateral: "text-muted-foreground", baixa: "text-destructive" } as const;

function distancia(v: number | null) {
  if (v === null) return null;
  return (
    <span className="text-xs text-muted-foreground">
      ({v > 0 ? "+" : v < 0 ? "−" : ""}
      {formatarNumero(Math.abs(v), 1)}%)
    </span>
  );
}

function Linha({ rotulo, preco, dist }: { rotulo: string; preco: number | null; dist?: number | null }) {
  if (preco === null) return null;
  return (
    <div className="flex items-baseline justify-between gap-2">
      <dt className="text-muted-foreground">{rotulo}</dt>
      <dd className="tabular-nums">
        {formatarPreco(preco)} {dist !== undefined && distancia(dist)}
      </dd>
    </div>
  );
}

function CartaoCenario({ c }: { c: CenarioPreco }) {
  const Icone = ICONE[c.tipo];
  return (
    <div className="grid content-start gap-3 rounded-xl border p-4">
      <div className="flex items-center gap-2">
        <Icone className={cn("size-5", COR[c.tipo])} aria-hidden />
        <h4 className="font-semibold">{c.titulo}</h4>
      </div>
      <dl className="grid gap-1 text-sm">
        {c.tipo === "lateral" ? (
          <>
            <Linha rotulo="Limite superior" preco={c.limite_superior} />
            <Linha rotulo="Limite inferior" preco={c.limite_inferior} />
          </>
        ) : (
          <>
            <Linha rotulo="Gatilho" preco={c.gatilho} dist={c.dist_gatilho} />
            <Linha rotulo="Próxima referência" preco={c.alvo} dist={c.dist_alvo} />
            <Linha rotulo="Invalidação" preco={c.invalidacao} dist={c.dist_invalidacao} />
            {c.relacao !== null && (
              <div className="flex items-baseline justify-between gap-2" title="Distância do gatilho à próxima referência dividida pela distância do gatilho à invalidação">
                <dt className="text-muted-foreground">Relação entre distâncias</dt>
                <dd className="tabular-nums">{formatarNumero(c.relacao, 1)}</dd>
              </div>
            )}
          </>
        )}
      </dl>
      <p className="text-sm text-muted-foreground">{c.texto}</p>
    </div>
  );
}

export function PainelCenarios({ dados }: { dados: CenariosAtivo }) {
  if (dados.cenarios.length === 0) return null;
  return (
    <section aria-labelledby="cenarios" className="grid gap-3">
      <div>
        <h3 id="cenarios" className="text-lg font-semibold">
          Cenários
        </h3>
        <p className="text-sm text-muted-foreground">
          Calculados a partir dos suportes e resistências semanais dos últimos 3 anos e da volatilidade média (ATR de 14 pregões:{" "}
          {formatarPreco(dados.atr14)}). São condições, não previsões: não indicam qual cenário é mais provável. Use o botão Níveis do gráfico
          para ver os níveis.
        </p>
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        {dados.cenarios.map((c) => (
          <CartaoCenario key={c.tipo} c={c} />
        ))}
      </div>
      <p className="text-xs text-muted-foreground">Níveis calculados com dados de {formatarData(dados.data)}.</p>
    </section>
  );
}

import { AlertTriangle, Info, TrendingDown, TrendingUp, type LucideIcon } from "lucide-react";

import { PainelCenarios } from "@/components/ativo/cenarios";
import { formatarData } from "@/lib/formato";
import type { AnaliseAtivo, InsightAtivo } from "@/lib/tipos-api";
import { cn } from "@/lib/utils";

const CATEGORIAS: { id: InsightAtivo["categoria"]; titulo: string }[] = [
  { id: "tendencia", titulo: "Tendência" },
  { id: "momento", titulo: "Momento" },
  { id: "volatilidade", titulo: "Volatilidade" },
  { id: "volume", titulo: "Volume" },
  { id: "fundamentos", titulo: "Fundamentos" },
  { id: "proventos", titulo: "Proventos" },
];

const TOM: Record<InsightAtivo["tom"], { icone: LucideIcon; classe: string; rotulo: string }> = {
  positivo: { icone: TrendingUp, classe: "text-positivo", rotulo: "Sinal positivo" },
  atencao: { icone: AlertTriangle, classe: "text-amber-600 dark:text-amber-400", rotulo: "Ponto de atenção" },
  neutro: { icone: Info, classe: "text-muted-foreground", rotulo: "Informativo" },
};

function CartaoTendencia({ insight }: { insight: InsightAtivo }) {
  const Icone = insight.tom === "positivo" ? TrendingUp : insight.tom === "atencao" ? TrendingDown : Info;
  return (
    <div className={cn("rounded-xl border p-5", insight.tom === "positivo" && "border-positivo/40", insight.tom === "atencao" && "border-destructive/40")}>
      <div className="flex items-center gap-2">
        <Icone className={cn("size-5", insight.tom === "atencao" ? "text-destructive" : TOM[insight.tom].classe)} aria-hidden />
        <h3 className="text-lg font-semibold">{insight.titulo}</h3>
      </div>
      <p className="mt-2 text-sm text-muted-foreground">{insight.texto}</p>
    </div>
  );
}

function ItemInsight({ insight }: { insight: InsightAtivo }) {
  const tom = TOM[insight.tom];
  return (
    <li className="flex gap-3">
      <tom.icone className={cn("mt-0.5 size-4 shrink-0", tom.classe)} aria-label={tom.rotulo} />
      <div>
        <p className="text-sm font-medium">{insight.titulo}</p>
        <p className="text-sm text-muted-foreground">{insight.texto}</p>
      </div>
    </li>
  );
}

export function PainelAnalise({ dados }: { dados: AnaliseAtivo | null }) {
  if (!dados || !dados.metricas) {
    return <p className="text-sm text-muted-foreground">A análise deste ativo ainda não foi calculada.</p>;
  }
  const tendencia = dados.insights.find((i) => i.codigo === "tendencia");
  const outros = dados.insights.filter((i) => i.codigo !== "tendencia");
  const grupos = CATEGORIAS.map((c) => ({ ...c, itens: outros.filter((i) => i.categoria === c.id) })).filter((g) => g.itens.length);

  return (
    <div className="grid gap-6">
      {!dados.elegivel && (
        <div className="rounded-lg border border-dashed p-4 text-sm">
          <p className="font-medium">Dados insuficientes para análise técnica confiável</p>
          <p className="mt-1 text-muted-foreground">{dados.motivo}</p>
        </div>
      )}
      {tendencia && <CartaoTendencia insight={tendencia} />}
      {grupos.length > 0 ? (
        <div className="grid gap-6 md:grid-cols-2">
          {grupos.map((g) => (
            <section key={g.id} aria-labelledby={`insights-${g.id}`}>
              <h3 id={`insights-${g.id}`} className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                {g.titulo}
              </h3>
              <ul className="grid gap-4">
                {g.itens.map((i) => (
                  <ItemInsight key={i.codigo} insight={i} />
                ))}
              </ul>
            </section>
          ))}
        </div>
      ) : (
        dados.elegivel && <p className="text-sm text-muted-foreground">Nenhum sinal técnico relevante no último pregão.</p>
      )}
      {dados.cenario && <PainelCenarios dados={dados.cenario} />}
      <p className="text-xs text-muted-foreground">
        Leituras automáticas dos indicadores com dados de {formatarData(dados.metricas.data)}. Elas descrevem o que os números mostram e não indicam
        o que fazer com o ativo.
      </p>
    </div>
  );
}

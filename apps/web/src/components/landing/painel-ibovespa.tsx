import { formatarData, formatarNumero, formatarPct } from "@/lib/formato";
import type { Indice } from "@/lib/tipos-api";
import { cn } from "@/lib/utils";

const L = 600;
const A = 240;

/** Gráfico do Ibovespa em 12 meses, desenhado no servidor como SVG. */
export function PainelIbovespa({ indice, className }: { indice: Indice; className?: string }) {
  const pontos = indice.pontos;
  if (pontos.length < 2) return null;
  const valores = pontos.map((p) => p.valor);
  const min = Math.min(...valores);
  const max = Math.max(...valores);
  const folga = (max - min) * 0.08 || 1;
  const y = (v: number) => A - ((v - (min - folga)) / (max - min + 2 * folga)) * A;
  const x = (i: number) => (i / (pontos.length - 1)) * L;
  const linha = pontos.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.valor).toFixed(1)}`).join("");
  const area = `${linha}L${L},${A}L0,${A}Z`;

  const ultimo = pontos.at(-1)!;
  const variacao = (ultimo.valor / pontos[0].valor - 1) * 100;
  const iMax = valores.indexOf(max);
  const iMin = valores.indexOf(min);

  return (
    <figure className={cn("grid gap-5 rounded-2xl border bg-card p-6 shadow-[0_1px_0_var(--border),0_12px_32px_-16px_rgb(10_11_15/0.18)]", className)}>
      <figcaption className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
        <div>
          <p className="text-sm text-muted-foreground">Ibovespa em 12 meses</p>
          <p className="font-display text-4xl font-semibold tracking-tight tabular-nums">{formatarNumero(ultimo.valor, 0)}</p>
        </div>
        <div className="text-right">
          <p className={cn("text-lg font-semibold tabular-nums", variacao >= 0 ? "text-positivo" : "text-destructive")}>{formatarPct(variacao)}</p>
          <p className="text-xs text-muted-foreground">até {formatarData(ultimo.data)}</p>
        </div>
      </figcaption>

      <div className="relative">
        <svg viewBox={`0 0 ${L} ${A}`} preserveAspectRatio="none" className="h-56 w-full overflow-visible" role="img" aria-label={`Gráfico do Ibovespa: de ${formatarNumero(pontos[0].valor, 0)} para ${formatarNumero(ultimo.valor, 0)} pontos`}>
          <defs>
            <linearGradient id="ibov-area" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--azul)" stopOpacity="0.22" />
              <stop offset="100%" stopColor="var(--azul)" stopOpacity="0" />
            </linearGradient>
          </defs>
          {[0.25, 0.5, 0.75].map((f) => (
            <line key={f} x1="0" x2={L} y1={A * f} y2={A * f} stroke="var(--border)" strokeDasharray="2 4" vectorEffect="non-scaling-stroke" />
          ))}
          <path d={area} fill="url(#ibov-area)" className="motion-safe:animate-[surgir_900ms_ease-out_400ms_both]" />
          <path
            d={linha}
            fill="none"
            stroke="var(--azul)"
            strokeWidth="2"
            strokeLinejoin="round"
            vectorEffect="non-scaling-stroke"
            pathLength={1}
            strokeDasharray="1"
            className="motion-safe:animate-[desenhar_1.4s_cubic-bezier(0.65,0,0.35,1)_both]"
          />
        </svg>
        <Marcador x={x(iMax) / L} y={y(max) / A} texto={`máx. ${formatarNumero(max, 0)}`} acima />
        <Marcador x={x(iMin) / L} y={y(min) / A} texto={`mín. ${formatarNumero(min, 0)}`} />
      </div>
    </figure>
  );
}

function Marcador({ x, y, texto, acima }: { x: number; y: number; texto: string; acima?: boolean }) {
  return (
    <span
      className={cn(
        "pointer-events-none absolute whitespace-nowrap rounded bg-card px-1.5 text-[11px] text-muted-foreground tabular-nums",
        acima ? "-translate-y-[130%]" : "translate-y-[30%]",
        x > 0.8 ? "-translate-x-full" : x < 0.2 ? "" : "-translate-x-1/2",
      )}
      style={{ left: `${x * 100}%`, top: `${y * 100}%` }}
    >
      {texto}
    </span>
  );
}

import { caminhoMiniatura } from "@/lib/mercado";
import { cn } from "@/lib/utils";

/** Minigráfico decorativo dos últimos 12 meses (o valor e as variações ficam no texto ao lado). */
export function Miniatura({ valores, className }: { valores: number[]; className?: string }) {
  const d = caminhoMiniatura(valores);
  if (!d) return null;
  const subiu = valores.at(-1)! >= valores[0];
  return (
    <svg viewBox="0 0 120 36" preserveAspectRatio="none" aria-hidden className={cn("h-9 w-full overflow-visible", className)}>
      <path
        d={d}
        fill="none"
        stroke={subiu ? "var(--positivo)" : "var(--destructive)"}
        strokeWidth="1.5"
        vectorEffect="non-scaling-stroke"
        strokeLinejoin="round"
      />
    </svg>
  );
}

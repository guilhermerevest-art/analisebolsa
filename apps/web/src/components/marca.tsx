import { cn } from "@/lib/utils";

/** Logotipo: três barras de candle subindo, em cobalto, ao lado do nome. */
export function Marca({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2 font-display text-[1.05rem] font-semibold tracking-tight", className)}>
      <svg viewBox="0 0 20 20" aria-hidden className="size-5 text-cobalto">
        <rect x="2" y="9" width="4" height="9" rx="1" fill="currentColor" opacity="0.45" />
        <rect x="8" y="5" width="4" height="13" rx="1" fill="currentColor" opacity="0.7" />
        <rect x="14" y="1" width="4" height="17" rx="1" fill="currentColor" />
      </svg>
      analisebolsa
    </span>
  );
}

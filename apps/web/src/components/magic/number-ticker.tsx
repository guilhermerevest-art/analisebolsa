"use client";

import { useEffect, useRef } from "react";

/**
 * Número que anima até o valor final (inspirado no NumberTicker do Magic UI).
 * Respeita prefers-reduced-motion e renderiza o valor final no servidor.
 */
export function NumberTicker({ valor, formatar, className }: { valor: number; formatar: (n: number) => string; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const inicio = performance.now();
    const duracao = 700;
    const de = valor * 0.97;
    let quadro = 0;
    const passo = (t: number) => {
      const p = Math.min(1, (t - inicio) / duracao);
      const suave = 1 - (1 - p) ** 3;
      el.textContent = formatar(de + (valor - de) * suave);
      if (p < 1) quadro = requestAnimationFrame(passo);
    };
    quadro = requestAnimationFrame(passo);
    return () => cancelAnimationFrame(quadro);
  }, [valor, formatar]);
  return (
    <span ref={ref} className={className} style={{ fontVariantNumeric: "tabular-nums" }}>
      {formatar(valor)}
    </span>
  );
}

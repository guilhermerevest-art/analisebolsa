"use client";

import { CircleHelp } from "lucide-react";
import { useCallback, useEffect, useId, useRef, useState } from "react";

import { GLOSSARIO, type ChaveGlossario } from "@/lib/glossario";
import { cn } from "@/lib/utils";

const LARGURA = 272;

/**
 * Explicação curta de um termo do glossário: abre ao passar o mouse, ao focar com o teclado
 * ou ao tocar (celular). A bolha é posicionada fixa na tela para não ser cortada por tabelas
 * com rolagem; fecha com Esc, ao rolar ou ao tocar fora.
 */
export function Dica({ termo, className }: { termo: ChaveGlossario; className?: string }) {
  const { titulo, curto } = GLOSSARIO[termo];
  const [aberta, setAberta] = useState(false);
  const [pos, setPos] = useState<{ left: number; top: number; acima: boolean } | null>(null);
  const botao = useRef<HTMLButtonElement>(null);
  const fixada = useRef(false);
  const id = useId();

  const abrir = useCallback(() => {
    const r = botao.current?.getBoundingClientRect();
    if (!r) return;
    const left = Math.min(Math.max(8, r.left + r.width / 2 - LARGURA / 2), window.innerWidth - LARGURA - 8);
    const acima = r.top > 180;
    setPos({ left, top: acima ? r.top - 8 : r.bottom + 8, acima });
    setAberta(true);
  }, []);
  const fechar = useCallback(() => {
    fixada.current = false;
    setAberta(false);
  }, []);

  useEffect(() => {
    if (!aberta) return;
    const tecla = (e: KeyboardEvent) => e.key === "Escape" && fechar();
    const fora = (e: PointerEvent) => !botao.current?.contains(e.target as Node) && fechar();
    window.addEventListener("keydown", tecla);
    window.addEventListener("scroll", fechar, { passive: true, capture: true });
    window.addEventListener("pointerdown", fora);
    return () => {
      window.removeEventListener("keydown", tecla);
      window.removeEventListener("scroll", fechar, { capture: true });
      window.removeEventListener("pointerdown", fora);
    };
  }, [aberta, fechar]);

  return (
    <span className={cn("inline-flex align-middle", className)}>
      <button
        ref={botao}
        type="button"
        aria-label={`O que é ${titulo}?`}
        aria-describedby={aberta ? id : undefined}
        aria-expanded={aberta}
        onMouseEnter={abrir}
        onMouseLeave={() => !fixada.current && setAberta(false)}
        onFocus={abrir}
        onBlur={fechar}
        onClick={() => {
          fixada.current = !aberta || !fixada.current;
          if (fixada.current) abrir();
          else fechar();
        }}
        className="-m-1 rounded-full p-1 text-muted-foreground transition-colors hover:text-azul focus-visible:text-azul focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <CircleHelp aria-hidden className="size-3.5" />
      </button>
      {aberta && pos && (
        <span
          id={id}
          role="tooltip"
          className={cn(
            "pointer-events-none fixed z-50 grid gap-1 rounded-lg border bg-card px-3 py-2.5 text-left text-xs font-normal normal-case leading-relaxed tracking-normal text-card-foreground shadow-lg",
            pos.acima && "-translate-y-full",
          )}
          style={{ left: pos.left, top: pos.top, width: LARGURA }}
        >
          <span className="font-semibold text-foreground">{titulo}</span>
          <span className="text-muted-foreground">{curto}</span>
        </span>
      )}
    </span>
  );
}

/** Rótulo com a dica ao lado: <Termo termo="sharpe">Índice de Sharpe</Termo>. */
export function Termo({ termo, children, className }: { termo: ChaveGlossario; children: React.ReactNode; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1", className)}>
      {children}
      <Dica termo={termo} />
    </span>
  );
}

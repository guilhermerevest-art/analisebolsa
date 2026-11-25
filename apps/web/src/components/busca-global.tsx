"use client";

import { Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { NOMES_TIPO } from "@/lib/formato";
import type { AtivoResumo, PaginaAtivos } from "@/lib/tipos-api";
import { cn } from "@/lib/utils";

/** Paleta de comandos (Ctrl+K / ⌘K) com autocomplete via /api/ativos?busca=. */
export function BuscaGlobal({ variante = "cabecalho" }: { variante?: "cabecalho" | "hero" }) {
  const [aberta, setAberta] = useState(false);
  const [termo, setTermo] = useState("");
  const [itens, setItens] = useState<AtivoResumo[]>([]);
  const [selecionado, setSelecionado] = useState(0);
  const dialogo = useRef<HTMLDialogElement>(null);
  const router = useRouter();

  const abrir = useCallback(() => setAberta(true), []);
  const fechar = useCallback(() => {
    setAberta(false);
    setTermo("");
    setItens([]);
  }, []);

  useEffect(() => {
    if (variante !== "cabecalho") return;
    const atalho = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setAberta((a) => !a);
      }
    };
    window.addEventListener("keydown", atalho);
    return () => window.removeEventListener("keydown", atalho);
  }, [variante]);

  useEffect(() => {
    const d = dialogo.current;
    if (!d) return;
    if (aberta && !d.open) d.showModal();
    if (!aberta && d.open) d.close();
  }, [aberta]);

  useEffect(() => {
    const t = termo.trim();
    if (!t) {
      setItens([]);
      return;
    }
    const controle = new AbortController();
    const espera = setTimeout(() => {
      fetch(`/api/ativos?busca=${encodeURIComponent(t)}&limite=8`, { signal: controle.signal })
        .then((r) => (r.ok ? (r.json() as Promise<PaginaAtivos>) : null))
        .then((r) => {
          setItens(r?.itens ?? []);
          setSelecionado(0);
        })
        .catch(() => {});
    }, 150);
    return () => {
      clearTimeout(espera);
      controle.abort();
    };
  }, [termo]);

  const ir = (ticker: string) => {
    fechar();
    router.push(`/ativo/${ticker}`);
  };

  const teclado = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelecionado((s) => Math.min(s + 1, itens.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelecionado((s) => Math.max(s - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const alvo = itens[selecionado]?.ticker ?? (/^[A-Za-z0-9]{4,6}$/.test(termo.trim()) ? termo.trim().toUpperCase() : null);
      if (alvo) ir(alvo);
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={abrir}
        className={cn(
          "flex items-center gap-2 rounded-md border text-muted-foreground transition-colors hover:bg-accent",
          variante === "hero" ? "h-12 w-full max-w-lg px-4 text-base shadow-sm" : "h-8 px-3 text-sm",
        )}
      >
        <Search aria-hidden className="size-4" />
        <span className="flex-1 text-left">{variante === "hero" ? "Busque por ticker ou empresa: PETR4, Vale, HGLG11..." : "Buscar ativo"}</span>
        {variante === "cabecalho" && <kbd className="hidden rounded border px-1.5 text-[10px] sm:inline">Ctrl K</kbd>}
      </button>
      <dialog
        ref={dialogo}
        onClose={fechar}
        onClick={(e) => e.target === dialogo.current && fechar()}
        className="m-auto mt-[15vh] w-[min(36rem,calc(100vw-2rem))] rounded-xl border bg-background p-0 text-foreground shadow-2xl backdrop:bg-black/40"
        aria-label="Buscar ativo"
      >
        <div className="flex items-center gap-2 border-b px-4">
          <Search aria-hidden className="size-4 text-muted-foreground" />
          <input
            autoFocus
            value={termo}
            onChange={(e) => setTermo(e.target.value)}
            onKeyDown={teclado}
            placeholder="Ticker ou nome da empresa"
            className="h-12 flex-1 bg-transparent outline-none"
            role="combobox"
            aria-expanded={itens.length > 0}
            aria-controls="resultados-busca"
            aria-activedescendant={itens[selecionado] ? `resultado-${itens[selecionado].ticker}` : undefined}
          />
        </div>
        <ul id="resultados-busca" role="listbox" className="max-h-80 overflow-auto p-2">
          {itens.map((a, i) => (
            <li
              key={a.ticker}
              id={`resultado-${a.ticker}`}
              role="option"
              aria-selected={i === selecionado}
              onMouseEnter={() => setSelecionado(i)}
              onClick={() => ir(a.ticker)}
              className={cn("flex cursor-pointer items-center gap-3 rounded-md px-3 py-2", i === selecionado && "bg-accent")}
            >
              <span className="w-16 font-semibold">{a.ticker}</span>
              <span className="flex-1 truncate text-sm text-muted-foreground">{a.nome}</span>
              <span className="text-xs text-muted-foreground">{NOMES_TIPO[a.tipo]}</span>
            </li>
          ))}
          {termo.trim() && itens.length === 0 && <li className="px-3 py-6 text-center text-sm text-muted-foreground">Nenhum ativo encontrado.</li>}
        </ul>
      </dialog>
    </>
  );
}

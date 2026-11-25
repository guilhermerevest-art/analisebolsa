"use client";

import { Star } from "lucide-react";
import Link from "next/link";
import { useEffect, useState, useTransition } from "react";

import { Button } from "@/components/ui/button";
import { alterarWatchlist } from "@/lib/acoes-watchlist";
import type { EstadoWatchlist } from "@/lib/tipos-api";
import { cn } from "@/lib/utils";

type Estado = "carregando" | "deslogado" | "fora" | "na_lista";

/** Estrela da watchlist. A página do ativo é cacheada, então o estado vem do BFF no cliente. */
export function EstrelaWatchlist({ ticker }: { ticker: string }) {
  const [estado, setEstado] = useState<Estado>("carregando");
  const [erro, setErro] = useState<string | null>(null);
  const [pendente, iniciar] = useTransition();

  useEffect(() => {
    let vivo = true;
    fetch(`/api/watchlist/${ticker}`, { cache: "no-store" })
      .then(async (r) => {
        if (!vivo) return;
        if (r.status === 401) return setEstado("deslogado");
        if (!r.ok) return setEstado("fora");
        const corpo = (await r.json()) as EstadoWatchlist;
        setEstado(corpo.na_lista ? "na_lista" : "fora");
      })
      .catch(() => vivo && setEstado("fora"));
    return () => {
      vivo = false;
    };
  }, [ticker]);

  if (estado === "deslogado") {
    return (
      <Button asChild variant="outline" size="sm">
        <Link href={`/entrar?voltar=/ativo/${ticker}`}>
          <Star aria-hidden />
          Watchlist
        </Link>
      </Button>
    );
  }

  const naLista = estado === "na_lista";
  const alternar = () => {
    setErro(null);
    setEstado(naLista ? "fora" : "na_lista");
    iniciar(async () => {
      const r = await alterarWatchlist(ticker, !naLista);
      setEstado(r.naLista ? "na_lista" : "fora");
      if (r.erro) setErro(r.erro);
    });
  };

  return (
    <div className="flex flex-col items-start gap-1">
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={alternar}
        disabled={estado === "carregando" || pendente}
        aria-pressed={naLista}
        title={naLista ? "Remover da watchlist" : "Adicionar à watchlist"}
      >
        <Star aria-hidden className={cn(naLista && "fill-amber-400 text-amber-500")} />
        {naLista ? "Na watchlist" : "Watchlist"}
      </Button>
      {erro && (
        <p role="alert" className="text-xs text-destructive">
          {erro}
        </p>
      )}
    </div>
  );
}

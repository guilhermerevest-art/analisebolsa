"use client";

import { useId, useState } from "react";

import { cn } from "@/lib/utils";

export function Abas({ abas }: { abas: { id: string; rotulo: string; conteudo: React.ReactNode }[] }) {
  const [ativa, setAtiva] = useState(abas[0]?.id);
  const base = useId();
  return (
    <div>
      <div role="tablist" className="flex gap-1 border-b">
        {abas.map((a) => (
          <button
            key={a.id}
            role="tab"
            id={`${base}-${a.id}`}
            aria-selected={ativa === a.id}
            aria-controls={`${base}-${a.id}-painel`}
            onClick={() => setAtiva(a.id)}
            className={cn(
              "-mb-px border-b-2 px-4 py-2 text-sm font-medium transition-colors",
              ativa === a.id ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {a.rotulo}
          </button>
        ))}
      </div>
      {abas.map((a) => (
        <div key={a.id} role="tabpanel" id={`${base}-${a.id}-painel`} aria-labelledby={`${base}-${a.id}`} hidden={ativa !== a.id} className="pt-6">
          {a.conteudo}
        </div>
      ))}
    </div>
  );
}

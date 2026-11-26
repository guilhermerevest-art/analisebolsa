"use client";

import { useRouter } from "next/navigation";
import type { FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { NOMES_TIPO } from "@/lib/formato";
import { LIQUIDEZ_PADRAO, TENDENCIAS, TIPOS } from "@/lib/screener";
import type { CampoScreener } from "@/lib/tipos-api";
import { classeSelect } from "@/components/ui/select-nativo";

type Props = {
  campos: CampoScreener[];
  setores: string[];
  valores: Record<string, string | string[] | undefined>;
};

const GRUPOS = [
  { id: "preco", titulo: "Preço e retorno" },
  { id: "tecnico", titulo: "Técnico e liquidez" },
  { id: "fundamentos", titulo: "Fundamentos" },
] as const;

const NOMES_TENDENCIA = { alta: "Alta", baixa: "Baixa", lateral: "Lateral" } as const;

function valor(v: string | string[] | undefined): string {
  return (Array.isArray(v) ? v[0] : v) ?? "";
}

function sufixo(unidade: CampoScreener["unidade"]): string {
  return unidade === "pct" ? "%" : unidade === "brl" ? "R$" : "";
}

function dica(c: CampoScreener): string | undefined {
  if (c.min === null || c.max === null) return undefined;
  const f = (n: number) => new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1, notation: c.unidade === "brl" ? "compact" : "standard" }).format(n);
  return `${f(c.min)} a ${f(c.max)}`;
}



export function FiltrosScreener({ campos, setores, valores }: Props) {
  const router = useRouter();
  const tiposMarcados = ([] as string[]).concat(valores.tipo ?? []);
  const semLiquidezPadrao = valor(valores.liquidez) === "todas";

  function aplicar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const dados = new FormData(e.currentTarget);
    const p = new URLSearchParams();
    for (const [k, v] of dados.entries()) {
      if (typeof v === "string" && v.trim() !== "") p.append(k, v.trim());
    }
    const ordem = valor(valores.ordem);
    if (ordem) p.set("ordem", ordem);
    router.push(p.size ? `/screener?${p.toString()}` : "/screener");
  }

  return (
    <form onSubmit={aplicar} className="grid gap-5" aria-label="Filtros do screener">
      <fieldset className="grid gap-2">
        <legend className="mb-1 text-sm font-medium">Tipo</legend>
        <div className="flex flex-wrap gap-3">
          {TIPOS.map((t) => (
            <label key={t} className="flex items-center gap-1.5 text-sm">
              <input type="checkbox" name="tipo" value={t} defaultChecked={tiposMarcados.includes(t)} />
              {NOMES_TIPO[t]}
            </label>
          ))}
        </div>
      </fieldset>

      <div className="grid grid-cols-2 gap-3">
        <label className="grid gap-1 text-sm">
          <span className="font-medium">Setor</span>
          <select name="setor" defaultValue={valor(valores.setor)} className={classeSelect}>
            <option value="">Todos</option>
            {setores.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-sm">
          <span className="font-medium">Tendência</span>
          <select name="tendencia" defaultValue={valor(valores.tendencia)} className={classeSelect}>
            <option value="">Todas</option>
            {TENDENCIAS.map((t) => (
              <option key={t} value={t}>
                {NOMES_TENDENCIA[t]}
              </option>
            ))}
          </select>
        </label>
      </div>

      <label className="flex items-start gap-2 text-sm">
        <input type="checkbox" name="liquidez" value="todas" defaultChecked={semLiquidezPadrao} className="mt-1" />
        <span>
          Incluir ativos com pouca negociação
          <span className="block text-xs text-muted-foreground">
            Sem isso, só entram ativos com liquidez média acima de R$ {LIQUIDEZ_PADRAO.toLocaleString("pt-BR")} por dia.
          </span>
        </span>
      </label>

      {GRUPOS.map((g) => (
        <details key={g.id} open={g.id !== "fundamentos" || campos.some((c) => c.grupo === g.id && (valores[`${c.campo}_min`] || valores[`${c.campo}_max`]))} className="group rounded-xl border bg-card p-3">
          <summary className="cursor-pointer text-sm font-medium">{g.titulo}</summary>
          <div className="mt-3 grid gap-3">
            {campos
              .filter((c) => c.grupo === g.id)
              .map((c) => (
                <div key={c.campo} className="grid gap-1">
                  <span className="text-sm" title={c.descricao}>
                    {c.rotulo} {sufixo(c.unidade) && <span className="text-xs text-muted-foreground">({sufixo(c.unidade)})</span>}
                  </span>
                  <div className="grid grid-cols-2 gap-2">
                    <input
                      name={`${c.campo}_min`}
                      inputMode="decimal"
                      aria-label={`${c.rotulo} mínimo`}
                      placeholder="mín."
                      defaultValue={valor(valores[`${c.campo}_min`])}
                      className={classeSelect}
                    />
                    <input
                      name={`${c.campo}_max`}
                      inputMode="decimal"
                      aria-label={`${c.rotulo} máximo`}
                      placeholder="máx."
                      defaultValue={valor(valores[`${c.campo}_max`])}
                      className={classeSelect}
                    />
                  </div>
                  {dica(c) && <span className="text-xs text-muted-foreground">Faixa comum: {dica(c)}</span>}
                </div>
              ))}
          </div>
        </details>
      ))}

      <div className="flex gap-2">
        <Button type="submit" className="flex-1">
          Aplicar filtros
        </Button>
        <Button type="button" variant="outline" onClick={() => router.push("/screener")}>
          Limpar
        </Button>
      </div>
    </form>
  );
}

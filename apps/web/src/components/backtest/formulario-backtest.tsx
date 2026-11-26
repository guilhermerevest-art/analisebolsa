"use client";

import { useState } from "react";

import { Campo } from "@/components/campo";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { ESTRATEGIAS, type EntradaBacktest, estrategiaPorCodigo, INICIO_MINIMO_BACKTEST, PRONTAS } from "@/lib/backtest";
import { cn } from "@/lib/utils";

const classeSelect = "h-9 w-full rounded-md border bg-background px-2 text-sm";

type Props = { inicial: EntradaBacktest; erros: Partial<Record<string, string>>; erroTicker?: string; mesMaximo: string };

/** Formulário GET: o estado vai para a URL. As estratégias prontas só preenchem os campos. */
export function FormularioBacktest({ inicial, erros, erroTicker, mesMaximo }: Props) {
  const [estrategia, setEstrategia] = useState(inicial.estrategia);
  const [parametros, setParametros] = useState(inicial.parametros);
  const atual = estrategiaPorCodigo(estrategia);
  const ativa = PRONTAS.find((p) => p.estrategia === estrategia && Object.entries(p.parametros).every(([k, v]) => parametros[k] === String(v)));

  return (
    <form method="get" action="/backtest" className="grid gap-5 rounded-lg border p-4">
      <fieldset className="grid gap-2">
        <legend className="mb-2 text-sm font-medium">Estratégias prontas</legend>
        <div className="flex flex-wrap gap-2">
          {PRONTAS.map((p) => (
            <button
              key={p.id}
              type="button"
              title={p.resumo}
              aria-pressed={ativa?.id === p.id}
              onClick={() => {
                setEstrategia(p.estrategia);
                setParametros((atuais) => ({ ...atuais, ...Object.fromEntries(Object.entries(p.parametros).map(([k, v]) => [k, String(v)])) }));
              }}
              className={cn(
                "rounded-full border px-3 py-1 text-sm transition-colors hover:bg-muted",
                ativa?.id === p.id && "border-primary bg-primary text-primary-foreground hover:bg-primary/90",
              )}
            >
              {p.nome}
            </button>
          ))}
        </div>
        {ativa && <p className="text-xs text-muted-foreground">{ativa.resumo}.</p>}
      </fieldset>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Campo
          nome="ticker"
          rotulo="Ativo"
          placeholder="PETR4"
          defaultValue={inicial.ticker}
          autoCapitalize="characters"
          autoComplete="off"
          maxLength={6}
          required
          erro={erros.ticker ?? erroTicker}
        />
        <div className="grid gap-2">
          <Label htmlFor="estrategia">Regra</Label>
          <select id="estrategia" name="estrategia" value={estrategia} onChange={(e) => setEstrategia(e.target.value)} className={classeSelect}>
            {ESTRATEGIAS.map((e) => (
              <option key={e.codigo} value={e.codigo}>
                {e.nome}
              </option>
            ))}
          </select>
        </div>
        <Campo nome="inicio" rotulo="Início" type="month" min={INICIO_MINIMO_BACKTEST} max={mesMaximo} defaultValue={inicial.inicio} required erro={erros.inicio} />
        <Campo nome="fim" rotulo="Fim (opcional)" type="month" min={INICIO_MINIMO_BACKTEST} max={mesMaximo} defaultValue={inicial.fim} erro={erros.fim} />
      </div>

      {atual.parametros.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {atual.parametros.map((p) => (
            <Campo
              key={p.chave}
              nome={p.chave}
              rotulo={p.rotulo}
              type="number"
              inputMode="numeric"
              min={p.minimo}
              max={p.maximo}
              step={1}
              value={parametros[p.chave] ?? ""}
              onChange={(e) => setParametros((atuais) => ({ ...atuais, [p.chave]: e.target.value }))}
              erro={erros[p.chave]}
            />
          ))}
        </div>
      )}

      <details className="group rounded-md border px-3 py-2" open={["stop", "capital", "corretagem", "taxas", "deslizamento"].some((c) => erros[c])}>
        <summary className="cursor-pointer text-sm font-medium">Stop, capital e custos</summary>
        <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <Campo nome="stop" rotulo="Stop (múltiplo do ATR)" inputMode="decimal" placeholder="Sem stop" defaultValue={inicial.stop} erro={erros.stop} />
          <Campo nome="capital" rotulo="Capital inicial (R$)" inputMode="decimal" defaultValue={inicial.capital} erro={erros.capital} />
          <Campo nome="corretagem" rotulo="Corretagem por ordem (R$)" inputMode="decimal" defaultValue={inicial.corretagem} erro={erros.corretagem} />
          <Campo nome="taxas" rotulo="Taxas da B3 (%)" inputMode="decimal" defaultValue={inicial.taxas} erro={erros.taxas} />
          <Campo nome="deslizamento" rotulo="Deslizamento (%)" inputMode="decimal" defaultValue={inicial.deslizamento} erro={erros.deslizamento} />
        </div>
        <div className="mt-3 flex items-center gap-2">
          <input type="hidden" name="cdi" value="0" />
          <input id="cdi" type="checkbox" name="cdi" value="1" defaultChecked={inicial.cdi} className="size-4 accent-primary" />
          <Label htmlFor="cdi" className="font-normal">
            Caixa rende o CDI fora da posição
          </Label>
        </div>
      </details>

      <div>
        <Button type="submit">Rodar o teste</Button>
      </div>
    </form>
  );
}

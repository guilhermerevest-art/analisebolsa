"use client";

import { useActionState, useEffect, useRef } from "react";

import { Campo } from "@/components/campo";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { type EstadoOperacao, lancarOperacao } from "@/lib/acoes-carteira";

export function FormularioOperacao({ carteira, hoje }: { carteira: number; hoje: string }) {
  const [estado, acao, pendente] = useActionState<EstadoOperacao, FormData>(lancarOperacao, {});
  const form = useRef<HTMLFormElement>(null);

  useEffect(() => {
    if (estado.ok) {
      form.current?.reset();
      form.current?.querySelector<HTMLInputElement>("[name=ticker]")?.focus();
    }
  }, [estado.ok]);

  return (
    <form ref={form} action={acao} className="grid gap-4" noValidate>
      <input type="hidden" name="carteira" value={carteira} />
      {estado.erros?.form && (
        <p role="alert" className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {estado.erros.form}
        </p>
      )}
      <fieldset className="flex gap-4 text-sm">
        <legend className="sr-only">Tipo de operação</legend>
        {(["compra", "venda"] as const).map((t) => (
          <Label key={t} className="flex items-center gap-2 font-normal">
            <input type="radio" name="tipo" value={t} defaultChecked={t === "compra"} className="accent-primary" />
            {t === "compra" ? "Compra" : "Venda"}
          </Label>
        ))}
      </fieldset>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Campo nome="ticker" rotulo="Ticker" placeholder="PETR4" autoCapitalize="characters" autoComplete="off" required erro={estado.erros?.ticker} />
        <Campo nome="data" rotulo="Data" type="date" max={hoje} defaultValue={hoje} required erro={estado.erros?.data} />
        <Campo nome="quantidade" rotulo="Quantidade" inputMode="decimal" placeholder="100" required erro={estado.erros?.quantidade} />
        <Campo nome="preco" rotulo="Preço (R$)" inputMode="decimal" placeholder="38,63" required erro={estado.erros?.preco} />
        <Campo nome="custos" rotulo="Custos (R$)" inputMode="decimal" placeholder="0,00" erro={estado.erros?.custos} />
        <div className="flex items-end">
          <Button type="submit" disabled={pendente} className="w-full">
            {pendente ? "Lançando..." : "Lançar"}
          </Button>
        </div>
      </div>
      <p className="text-xs text-muted-foreground">Custos são corretagem e taxas da nota; entram no preço médio.</p>
    </form>
  );
}

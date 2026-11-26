"use client";

import Link from "next/link";
import { useActionState, useEffect, useRef } from "react";

import { Campo } from "@/components/campo";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { editarOperacao, type EstadoOperacao, lancarOperacao } from "@/lib/acoes-carteira";
import type { OperacaoCarteira } from "@/lib/tipos-api";

/** Número da API ("38.6300") no formato do campo ("38,63"), sem ambiguidade de milhar. */
const campo = (v: string) => {
  const [inteiro, frac = ""] = v.split(".");
  const f = frac.replace(/0+$/, "");
  return f ? `${inteiro},${f}` : inteiro;
};

type Props = { carteira: number; hoje: string; operacao?: OperacaoCarteira };

export function FormularioOperacao({ carteira, hoje, operacao }: Props) {
  const [estado, acao, pendente] = useActionState<EstadoOperacao, FormData>(operacao ? editarOperacao : lancarOperacao, {});
  const form = useRef<HTMLFormElement>(null);

  useEffect(() => {
    if (operacao) form.current?.querySelector<HTMLInputElement>("[name=quantidade]")?.focus();
  }, [operacao]);

  useEffect(() => {
    if (estado.ok && !operacao) {
      form.current?.reset();
      form.current?.querySelector<HTMLInputElement>("[name=ticker]")?.focus();
    }
  }, [estado.ok, operacao]);

  return (
    <form ref={form} action={acao} className="grid gap-4" noValidate>
      <input type="hidden" name="carteira" value={carteira} />
      {operacao && <input type="hidden" name="operacao" value={operacao.id} />}
      {estado.erros?.form && (
        <p role="alert" className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {estado.erros.form}
        </p>
      )}
      <fieldset className="flex gap-4 text-sm">
        <legend className="sr-only">Tipo de operação</legend>
        {(["compra", "venda"] as const).map((t) => (
          <Label key={t} className="flex items-center gap-2 font-normal">
            <input type="radio" name="tipo" value={t} defaultChecked={t === (operacao?.tipo ?? "compra")} className="accent-primary" />
            {t === "compra" ? "Compra" : "Venda"}
          </Label>
        ))}
      </fieldset>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Campo nome="ticker" rotulo="Ticker" placeholder="PETR4" autoCapitalize="characters" autoComplete="off" required defaultValue={operacao?.ticker} erro={estado.erros?.ticker} />
        <Campo nome="data" rotulo="Data" type="date" max={hoje} defaultValue={operacao?.data ?? hoje} required erro={estado.erros?.data} />
        <Campo nome="quantidade" rotulo="Quantidade" inputMode="decimal" placeholder="100" required defaultValue={operacao && campo(operacao.quantidade)} erro={estado.erros?.quantidade} />
        <Campo nome="preco" rotulo="Preço (R$)" inputMode="decimal" placeholder="38,63" required defaultValue={operacao && campo(operacao.preco)} erro={estado.erros?.preco} />
        <Campo nome="custos" rotulo="Custos (R$)" inputMode="decimal" placeholder="0,00" defaultValue={operacao && campo(operacao.custos)} erro={estado.erros?.custos} />
        <div className="flex items-end gap-2">
          <Button type="submit" disabled={pendente} className="w-full">
            {operacao ? (pendente ? "Salvando..." : "Salvar") : pendente ? "Lançando..." : "Lançar"}
          </Button>
          {operacao && (
            <Button asChild variant="ghost">
              <Link href={`/carteira?c=${carteira}`}>Cancelar</Link>
            </Button>
          )}
        </div>
      </div>
      <p className="text-xs text-muted-foreground">Custos são corretagem e taxas da nota; entram no preço médio.</p>
    </form>
  );
}

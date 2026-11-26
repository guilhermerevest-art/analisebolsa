"use client";

import { useActionState } from "react";

import { Campo } from "@/components/campo";
import { Button } from "@/components/ui/button";
import { type EstadoForm, entrar } from "@/lib/acoes";

export function FormularioEntrar({ voltar }: { voltar?: string }) {
  const [estado, acao, pendente] = useActionState<EstadoForm, FormData>(entrar, {});
  return (
    <form action={acao} className="grid gap-4" noValidate>
      {voltar && <input type="hidden" name="voltar" value={voltar} />}
      {estado.erros?.form && (
        <p role="alert" className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {estado.erros.form}
        </p>
      )}
      <Campo
        nome="email"
        rotulo="E-mail"
        type="email"
        autoComplete="email"
        required
        defaultValue={estado.valores?.email}
        erro={estado.erros?.email}
      />
      <Campo nome="senha" rotulo="Senha" type="password" autoComplete="current-password" required erro={estado.erros?.senha} />
      <Button type="submit" disabled={pendente}>
        {pendente ? "Entrando…" : "Entrar"}
      </Button>
    </form>
  );
}

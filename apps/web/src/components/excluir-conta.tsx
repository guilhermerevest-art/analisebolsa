"use client";

import { useActionState } from "react";

import { Campo } from "@/components/campo";
import { Button } from "@/components/ui/button";
import { type EstadoExclusao, excluirConta } from "@/lib/acoes-conta";

export function ExcluirConta() {
  const [estado, acao, pendente] = useActionState<EstadoExclusao, FormData>(excluirConta, {});
  return (
    <form action={acao} className="grid gap-3">
      <Campo nome="confirmacao" rotulo='Digite "excluir" para confirmar' autoComplete="off" erro={estado.erro} />
      <Button type="submit" variant="outline" className="text-destructive" disabled={pendente}>
        {pendente ? "Excluindo…" : "Excluir minha conta e todos os dados"}
      </Button>
    </form>
  );
}

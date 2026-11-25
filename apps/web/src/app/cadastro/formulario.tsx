"use client";

import { useActionState } from "react";

import { Campo } from "@/components/campo";
import { Button } from "@/components/ui/button";
import { type EstadoForm, cadastrar } from "@/lib/acoes";
import { SENHA_MINIMA } from "@/lib/constantes";

export function FormularioCadastro() {
  const [estado, acao, pendente] = useActionState<EstadoForm, FormData>(cadastrar, {});
  return (
    <form action={acao} className="grid gap-4" noValidate>
      <Campo nome="nome" rotulo="Nome" autoComplete="name" required defaultValue={estado.valores?.nome} erro={estado.erros?.nome} />
      <Campo
        nome="email"
        rotulo="E-mail"
        type="email"
        autoComplete="email"
        required
        defaultValue={estado.valores?.email}
        erro={estado.erros?.email}
      />
      <Campo
        nome="senha"
        rotulo={`Senha (mínimo de ${SENHA_MINIMA} caracteres)`}
        type="password"
        autoComplete="new-password"
        minLength={SENHA_MINIMA}
        required
        erro={estado.erros?.senha}
      />
      <Campo
        nome="confirmacao"
        rotulo="Confirme a senha"
        type="password"
        autoComplete="new-password"
        required
        erro={estado.erros?.confirmacao}
      />
      <Button type="submit" disabled={pendente}>
        {pendente ? "Criando conta..." : "Criar conta"}
      </Button>
    </form>
  );
}

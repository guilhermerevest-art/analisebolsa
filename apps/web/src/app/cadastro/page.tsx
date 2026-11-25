import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { auth } from "@/auth";
import { BotaoGoogle } from "@/components/botao-google";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { googleHabilitado } from "@/lib/env";
import { FormularioCadastro } from "./formulario";

export const metadata: Metadata = { title: "Criar conta" };

export default async function Cadastro() {
  if ((await auth())?.user) redirect("/conta");
  return (
    <Card className="mx-auto w-full max-w-sm">
      <CardHeader>
        <CardTitle className="text-2xl">Criar conta</CardTitle>
        <CardDescription>É grátis.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <FormularioCadastro />
        {googleHabilitado() && <BotaoGoogle />}
      </CardContent>
      <CardFooter className="text-sm text-muted-foreground">
        Já tem conta?&nbsp;
        <Link href="/entrar" className="underline underline-offset-4">
          Entrar
        </Link>
      </CardFooter>
    </Card>
  );
}

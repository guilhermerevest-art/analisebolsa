import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { auth } from "@/auth";
import { BotaoGoogle } from "@/components/botao-google";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { googleHabilitado } from "@/lib/env";
import { destinoSeguro } from "@/lib/validacao";
import { FormularioEntrar } from "./formulario";

export const metadata: Metadata = { title: "Entrar" };

type Props = { searchParams: Promise<{ voltar?: string }> };

export default async function Entrar({ searchParams }: Props) {
  const voltar = destinoSeguro((await searchParams).voltar);
  if ((await auth())?.user) redirect(voltar);
  return (
    <Card className="mx-auto w-full max-w-sm">
      <CardHeader>
        <CardTitle className="text-2xl">Entrar</CardTitle>
        <CardDescription>Acesse sua conta do analisebolsa.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <FormularioEntrar voltar={voltar} />
        {googleHabilitado() && <BotaoGoogle voltar={voltar} />}
      </CardContent>
      <CardFooter className="text-sm text-muted-foreground">
        Não tem conta?&nbsp;
        <Link href="/cadastro" className="underline underline-offset-4">
          Criar conta
        </Link>
      </CardFooter>
    </Card>
  );
}

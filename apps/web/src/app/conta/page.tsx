import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { auth } from "@/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { sair } from "@/lib/acoes";

export const metadata: Metadata = { title: "Minha conta" };

export default async function Conta() {
  const sessao = await auth();
  if (!sessao?.user) redirect("/entrar");
  const { name, email, plano, role } = sessao.user;
  return (
    <Card className="mx-auto w-full max-w-md">
      <CardHeader>
        <CardTitle className="text-2xl">Minha conta</CardTitle>
        <CardDescription>Seus dados no analisebolsa.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-6">
        <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
          <dt className="text-muted-foreground">Nome</dt>
          <dd>{name ?? "—"}</dd>
          <dt className="text-muted-foreground">E-mail</dt>
          <dd>{email}</dd>
          <dt className="text-muted-foreground">Plano</dt>
          <dd className="capitalize">{plano === "free" ? "Grátis" : plano}</dd>
          {role === "admin" && (
            <>
              <dt className="text-muted-foreground">Perfil</dt>
              <dd>Administrador</dd>
            </>
          )}
        </dl>
        <form action={sair}>
          <Button type="submit" variant="outline">
            Sair
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

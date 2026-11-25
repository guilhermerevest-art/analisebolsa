import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { auth } from "@/auth";
import { Button } from "@/components/ui/button";
import { ExcluirConta } from "@/components/excluir-conta";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { sair } from "@/lib/acoes";

export const metadata: Metadata = { title: "Minha conta" };

export default async function Conta() {
  const sessao = await auth();
  if (!sessao?.user) redirect("/entrar");
  const { name, email, plano, role } = sessao.user;
  return (
    <div className="mx-auto grid w-full max-w-md gap-6">
      <Card>
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
            <dd className="capitalize">
              {plano === "free" ? "Grátis" : plano}
            </dd>
            {role === "admin" && (
              <>
                <dt className="text-muted-foreground">Perfil</dt>
                <dd>Administrador</dd>
              </>
            )}
          </dl>
          <nav aria-label="Atalhos da conta" className="flex flex-wrap gap-2">
            {[
              ["/carteira", "Carteira"],
              ["/watchlist", "Watchlist"],
              ["/alertas", "Alertas"],
            ].map(([href, rotulo]) => (
              <Button key={href} asChild variant="outline" size="sm">
                <Link href={href}>{rotulo}</Link>
              </Button>
            ))}
          </nav>
          <form action={sair}>
            <Button type="submit" variant="outline">
              Sair
            </Button>
          </form>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Seus dados</CardTitle>
          <CardDescription>
            Baixe tudo o que está guardado na sua conta, ou exclua a conta. A
            exclusão apaga carteiras, operações, watchlist e alertas, e não pode
            ser desfeita.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-6">
          <Button asChild variant="outline">
            <a href="/conta/exportar" download>
              Exportar meus dados (JSON)
            </a>
          </Button>
          <ExcluirConta />
        </CardContent>
      </Card>
    </div>
  );
}

import Link from "next/link";

import { auth } from "@/auth";
import { BuscaGlobal } from "@/components/busca-global";
import { Marca } from "@/components/marca";
import { MenuCelular } from "@/components/menu-celular";
import { Button } from "@/components/ui/button";

export async function Cabecalho() {
  const sessao = await auth().catch(() => null);
  const logado = Boolean(sessao?.user);
  const links = [
    { href: "/mercado", rotulo: "Mercado" },
    { href: "/screener", rotulo: "Screener" },
    { href: "/comparar", rotulo: "Comparar ativos", curto: "Comparar" },
    { href: "/simulador", rotulo: "Simulador" },
    { href: "/backtest", rotulo: "Backtest" },
    { href: "/posicao", rotulo: "Calculadora de posição", curto: "Posição" },
    { href: "/glossario", rotulo: "Glossário" },
    ...(logado
      ? [
          { href: "/watchlist", rotulo: "Watchlist" },
          { href: "/carteira", rotulo: "Carteira" },
          { href: "/alertas", rotulo: "Alertas" },
        ]
      : []),
    ...(sessao?.user?.role === "admin" ? [{ href: "/admin", rotulo: "Admin" }] : []),
  ];

  return (
    <header className="sticky top-0 z-40 border-b bg-background/85 backdrop-blur supports-[backdrop-filter]:bg-background/70">
      <div className="relative mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4">
        <Link href="/" aria-label="analisebolsa, página inicial" className="shrink-0">
          <Marca />
        </Link>
        <div className="flex items-center gap-1">
          <BuscaGlobal />
          <nav aria-label="Principal" className="hidden items-center gap-0.5 xl:flex">
            {links.map((l) => (
              <Button key={l.href} asChild variant="ghost" size="sm">
                <Link href={l.href}>{"curto" in l ? l.curto : l.rotulo}</Link>
              </Button>
            ))}
          </nav>
          {logado ? (
            <Button asChild variant="outline" size="sm" className="ml-1">
              <Link href="/conta">Minha conta</Link>
            </Button>
          ) : (
            <>
              <Button asChild variant="ghost" size="sm">
                <Link href="/entrar">Entrar</Link>
              </Button>
              <Button asChild size="sm">
                <Link href="/cadastro">Criar conta</Link>
              </Button>
            </>
          )}
          <MenuCelular links={links.map(({ href, rotulo }) => ({ href, rotulo }))} />
        </div>
      </div>
    </header>
  );
}

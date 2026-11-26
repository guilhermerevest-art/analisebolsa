import Link from "next/link";

import { auth } from "@/auth";
import { BuscaGlobal } from "@/components/busca-global";
import { Marca } from "@/components/marca";
import { Button } from "@/components/ui/button";

export async function Cabecalho() {
  const sessao = await auth().catch(() => null);
  return (
    <header className="sticky top-0 z-40 border-b bg-background/85 backdrop-blur supports-[backdrop-filter]:bg-background/70">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4">
        <Link href="/" aria-label="analisebolsa, página inicial" className="shrink-0">
          <Marca />
        </Link>
        <nav aria-label="Principal" className="flex items-center gap-1">
          <BuscaGlobal />
          <Button asChild variant="ghost" size="sm" className="hidden sm:inline-flex">
            <Link href="/screener">Screener</Link>
          </Button>
          <Button asChild variant="ghost" size="sm" className="hidden md:inline-flex">
            <Link href="/simulador">Simulador</Link>
          </Button>
          <Button asChild variant="ghost" size="sm" className="hidden md:inline-flex">
            <Link href="/backtest">Backtest</Link>
          </Button>
          {sessao?.user && (
            <Button asChild variant="ghost" size="sm" className="hidden sm:inline-flex">
              <Link href="/watchlist">Watchlist</Link>
            </Button>
          )}
          {sessao?.user && (
            <Button asChild variant="ghost" size="sm" className="hidden sm:inline-flex">
              <Link href="/carteira">Carteira</Link>
            </Button>
          )}
          {sessao?.user && (
            <Button asChild variant="ghost" size="sm" className="hidden lg:inline-flex">
              <Link href="/alertas">Alertas</Link>
            </Button>
          )}
          {sessao?.user?.role === "admin" && (
            <Button asChild variant="ghost" size="sm">
              <Link href="/admin">Admin</Link>
            </Button>
          )}
          {sessao?.user ? (
            <Button asChild variant="outline" size="sm">
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
        </nav>
      </div>
    </header>
  );
}

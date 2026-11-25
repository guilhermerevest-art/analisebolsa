import Link from "next/link";

import { auth } from "@/auth";
import { BuscaGlobal } from "@/components/busca-global";
import { Button } from "@/components/ui/button";

export async function Cabecalho() {
  const sessao = await auth().catch(() => null);
  return (
    <header className="border-b">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
        <Link href="/" className="font-semibold tracking-tight">
          analisebolsa
        </Link>
        <nav className="flex items-center gap-2">
          <BuscaGlobal />
          <Button asChild variant="ghost" size="sm" className="hidden sm:inline-flex">
            <Link href="/screener">Screener</Link>
          </Button>
          <Button asChild variant="ghost" size="sm" className="hidden md:inline-flex">
            <Link href="/simulador">Simulador</Link>
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

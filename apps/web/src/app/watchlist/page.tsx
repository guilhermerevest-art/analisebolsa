import { X } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { auth } from "@/auth";
import { COLUNAS } from "@/components/screener/tabela";
import { Button } from "@/components/ui/button";
import { removerDaWatchlist } from "@/lib/acoes-watchlist";
import { chamarApi } from "@/lib/api";
import type { ItemScreener, Watchlist } from "@/lib/tipos-api";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Minha watchlist", robots: { index: false } };
export const dynamic = "force-dynamic";

async function lerWatchlist(): Promise<Watchlist | null> {
  const resp = await chamarApi("/v1/watchlist", { cache: "no-store" });
  if (resp.status === 401) redirect("/entrar?voltar=/watchlist");
  if (!resp.ok) return null;
  return (await resp.json()) as Watchlist;
}

export default async function PaginaWatchlist() {
  if (!(await auth())?.user) redirect("/entrar?voltar=/watchlist");
  const dados = await lerWatchlist();

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Minha watchlist</h1>
        <p className="mt-1 text-muted-foreground">
          Os ativos que você acompanha, com os dados do último pregão. Adicione pela estrela na página de cada ativo.
        </p>
      </div>

      {!dados ? (
        <p role="alert" className="text-sm text-destructive">
          Não foi possível carregar a watchlist agora. Tente de novo em instantes.
        </p>
      ) : dados.itens.length === 0 ? (
        <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
          <p>Sua watchlist está vazia.</p>
          <p className="mt-2">
            Use a busca (Ctrl+K) ou o{" "}
            <Link href="/screener" className="underline underline-offset-4">
              screener
            </Link>{" "}
            para encontrar ativos e toque na estrela para adicioná-los.
          </p>
        </div>
      ) : (
        <>
          <div className="relative overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-muted-foreground">
                <tr>
                  <th scope="col" className="py-2 text-left font-normal">
                    Ativo
                  </th>
                  {COLUNAS.map((c) => (
                    <th key={c.chave} scope="col" title={c.titulo} className={cn("whitespace-nowrap py-2 pl-3 text-right font-normal", c.classe)}>
                      {c.rotulo}
                    </th>
                  ))}
                  <th scope="col" className="w-10">
                    <span className="sr-only">Remover</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {dados.itens.map((i) => {
                  const linha = i.metricas ? ({ ...i, ...i.metricas } as ItemScreener) : null;
                  return (
                    <tr key={i.ticker} className="border-t hover:bg-muted/40">
                      <td className="py-2 pr-3">
                        <Link href={`/ativo/${i.ticker}`} className="font-semibold hover:underline">
                          {i.ticker}
                        </Link>
                        <span className="block max-w-48 truncate text-xs text-muted-foreground">{i.nome}</span>
                      </td>
                      {COLUNAS.map((c) => (
                        <td key={c.chave} className={cn("whitespace-nowrap py-2 pl-3 text-right tabular-nums", c.classe)}>
                          {linha ? c.render(linha) : "—"}
                        </td>
                      ))}
                      <td className="py-2 pl-2 text-right">
                        <form action={removerDaWatchlist}>
                          <input type="hidden" name="ticker" value={i.ticker} />
                          <Button type="submit" variant="ghost" size="icon" className="size-8" title={`Remover ${i.ticker}`}>
                            <X aria-hidden />
                            <span className="sr-only">Remover {i.ticker}</span>
                          </Button>
                        </form>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-muted-foreground">
            {dados.itens.length} de {dados.limite} ativos.
          </p>
        </>
      )}
    </div>
  );
}

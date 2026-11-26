import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { auth } from "@/auth";
import { ImportadorB3 } from "@/components/carteira/importador-b3";
import { chamarApi } from "@/lib/api";
import type { Carteiras } from "@/lib/tipos-api";

export const metadata: Metadata = { title: "Importar da B3", robots: { index: false } };
export const dynamic = "force-dynamic";

type Props = { searchParams: Promise<{ c?: string }> };

export default async function PaginaImportar({ searchParams }: Props) {
  if (!(await auth())?.user) redirect("/entrar?voltar=/carteira");
  const resp = await chamarApi("/v1/carteiras", { cache: "no-store" });
  if (resp.status === 401) redirect("/entrar?voltar=/carteira");
  if (!resp.ok) throw new Error(`API ${resp.status} em /v1/carteiras`);
  const lista = (await resp.json()) as Carteiras;
  if (lista.itens.length === 0) redirect("/carteira");
  const pedida = Number((await searchParams).c);
  const carteira = Number.isInteger(pedida) && pedida > 0 ? lista.itens.find((c) => c.id === pedida) : lista.itens[0];
  if (!carteira) notFound();

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-8">
      <div>
        <Link href={`/carteira?c=${carteira.id}`} className="text-sm text-muted-foreground hover:text-foreground">
          Voltar para {carteira.nome}
        </Link>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">Importar operações da B3</h1>
        <p className="mt-1 max-w-2xl text-muted-foreground">
          Traga as compras e vendas do extrato de negociação da B3 para a carteira {carteira.nome}. Você vê tudo antes de confirmar, e o que já está
          na carteira não é lançado de novo.
        </p>
      </div>

      <section aria-labelledby="titulo-passos" className="grid gap-3 rounded-xl border bg-card p-5">
        <h2 id="titulo-passos" className="font-semibold">
          Como baixar o extrato
        </h2>
        <ol className="grid list-decimal gap-1.5 pl-5 text-sm text-muted-foreground marker:text-foreground">
          <li>
            Entre na Área do Investidor da B3 (<span className="font-medium text-foreground">investidor.b3.com.br</span>) com sua conta gov.br.
          </li>
          <li>Abra Extratos e escolha a aba Negociação.</li>
          <li>Filtre o período desde a sua primeira compra e baixe em Excel (.xlsx).</li>
          <li>Envie o arquivo aqui embaixo.</li>
        </ol>
        <p className="text-xs text-muted-foreground">
          O extrato não traz corretagem nem taxas, então as operações entram com custo zero. Opções, termo e futuros ficam de fora.
        </p>
      </section>

      <ImportadorB3 carteira={carteira.id} />
    </div>
  );
}

import type { Metadata } from "next";
import Link from "next/link";

import { FiltrosScreener } from "@/components/screener/filtros";
import { TabelaScreener } from "@/components/screener/tabela";
import { Button } from "@/components/ui/button";
import { lerCamposScreener, lerScreener } from "@/lib/dados";
import { formatarData, formatarNumero } from "@/lib/formato";
import { LIMITE, paramsParaApi, PRESETS, urlCom, urlPreset } from "@/lib/screener";
import { cn } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Screener de ações, FIIs, ETFs e BDRs",
  description: "Filtre os ativos da B3 por variação, tendência, volatilidade, liquidez, P/L, P/VP, dividend yield, ROE e mais.",
  alternates: { canonical: "/screener" },
};

type Props = { searchParams: Promise<Record<string, string | string[] | undefined>> };

export default async function Screener({ searchParams }: Props) {
  const busca = await searchParams;
  const qs = paramsParaApi(busca);
  const [resultado, campos] = await Promise.all([lerScreener(qs).catch(() => null), lerCamposScreener().catch(() => null)]);
  const pagina = Number(qs.get("pagina"));
  const ordem = qs.get("ordem") ?? "";
  const total = resultado?.total ?? 0;
  const paginas = Math.max(1, Math.ceil(total / LIMITE));
  const atual = new URLSearchParams(Object.entries(busca).flatMap(([k, v]) => ([] as string[]).concat(v ?? []).map((i) => [k, i]))).toString();

  return (
    <div className="grid gap-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Screener</h1>
        <p className="mt-1 text-muted-foreground">Filtre os ativos da B3 por indicadores técnicos e fundamentos. Os dados são do último pregão.</p>
      </div>

      <nav aria-label="Filtros prontos" className="flex flex-wrap gap-2">
        {PRESETS.map((p) => {
          const ativo = new URLSearchParams(p.params).toString() === atual;
          return (
            <Link
              key={p.id}
              href={urlPreset(p)}
              title={p.descricao}
              className={cn("rounded-full border px-3 py-1 text-sm hover:bg-muted", ativo && "border-foreground bg-muted font-medium")}
            >
              {p.titulo}
            </Link>
          );
        })}
      </nav>
      {PRESETS.filter((p) => new URLSearchParams(p.params).toString() === atual).map((p) => (
        <p key={p.id} className="-mt-3 max-w-3xl text-sm text-muted-foreground">
          {p.descricao}. Filtro sobre os dados do último pregão, para estudo.
        </p>
      ))}

      <div className="grid gap-6 lg:grid-cols-[18rem_1fr]">
        <aside className="order-2 lg:order-none">
          {campos ? (
            <details open className="lg:[&>summary]:hidden">
              <summary className="mb-3 cursor-pointer rounded-md border px-3 py-2 text-sm font-medium">Filtros</summary>
              <FiltrosScreener key={atual} campos={campos.campos} setores={campos.setores} valores={busca} />
            </details>
          ) : (
            <p className="text-sm text-muted-foreground">Filtros indisponíveis no momento.</p>
          )}
        </aside>

        <section aria-live="polite" className="grid min-w-0 content-start gap-4">
          {resultado === null ? (
            <p className="rounded-lg border p-6 text-sm text-muted-foreground">Não foi possível carregar o screener agora. Tente de novo em instantes.</p>
          ) : total === 0 ? (
            <div className="rounded-lg border p-6 text-sm">
              <p className="font-medium">Nenhum ativo passa nesses filtros.</p>
              <p className="mt-1 text-muted-foreground">Afrouxe algum limite ou inclua os ativos com pouca negociação.</p>
            </div>
          ) : (
            <>
              <p className="text-sm text-muted-foreground">
                {formatarNumero(total, 0)} {total === 1 ? "ativo" : "ativos"}
                {resultado.itens[0] && <> · dados de {formatarData(resultado.itens[0].data)}</>}
              </p>
              <TabelaScreener itens={resultado.itens} ordem={ordem} busca={busca} />
              {paginas > 1 && (
                <nav aria-label="Paginação" className="flex items-center justify-between text-sm">
                  <Button asChild variant="outline" size="sm" className={cn(pagina <= 1 && "pointer-events-none opacity-50")}>
                    <Link href={urlCom(busca, { pagina: String(pagina - 1) })} aria-disabled={pagina <= 1}>
                      Anterior
                    </Link>
                  </Button>
                  <span className="text-muted-foreground">
                    Página {pagina} de {paginas}
                  </span>
                  <Button asChild variant="outline" size="sm" className={cn(pagina >= paginas && "pointer-events-none opacity-50")}>
                    <Link href={urlCom(busca, { pagina: String(pagina + 1) })} aria-disabled={pagina >= paginas}>
                      Próxima
                    </Link>
                  </Button>
                </nav>
              )}
            </>
          )}
        </section>
      </div>

    </div>
  );
}

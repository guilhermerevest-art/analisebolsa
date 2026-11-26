import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { auth } from "@/auth";
import { Copiar } from "@/components/copiar";
import { Button } from "@/components/ui/button";
import { chamarApi } from "@/lib/api";
import { formatarNumero, formatarPreco } from "@/lib/formato";
import type { Carteiras, DeclaracaoCarteira } from "@/lib/tipos-api";
import { cn } from "@/lib/utils";
import { Termo } from "@/components/dica";
import type { ChaveGlossario } from "@/lib/glossario";

export const metadata: Metadata = { title: "Declaração anual", robots: { index: false } };
export const dynamic = "force-dynamic";

type Props = { searchParams: Promise<{ c?: string; ano?: string }> };
type Rendimento = DeclaracaoCarteira["dividendos"][number];

async function ler<T>(caminho: string): Promise<T | null> {
  const resp = await chamarApi(caminho, { cache: "no-store" });
  if (resp.status === 401) redirect("/entrar?voltar=/carteira");
  return resp.ok ? ((await resp.json()) as T) : null;
}

const qtd = (v: string) => formatarNumero(v, Number.isInteger(Number(v)) ? 0 : 4);
const soma = (itens: Rendimento[], campo: "bruto" | "ir" | "liquido") => String(itens.reduce((t, r) => t + Number(r[campo]), 0));

function Ficha({ titulo, onde, termo, children }: { titulo: string; onde: string; termo?: ChaveGlossario; children: React.ReactNode }) {
  return (
    <section className="grid gap-3">
      <div>
        <h2 className="text-xl font-semibold">{termo ? <Termo termo={termo}>{titulo}</Termo> : titulo}</h2>
        <p className="text-sm text-muted-foreground">{onde}</p>
      </div>
      {children}
    </section>
  );
}

function TabelaRendimentos({ itens, comIr, vazio }: { itens: Rendimento[]; comIr?: boolean; vazio: string }) {
  if (itens.length === 0) return <p className="rounded-xl border bg-card p-4 text-sm text-muted-foreground">{vazio}</p>;
  return (
    <div className="overflow-x-auto rounded-xl border bg-card">
      <table className="w-full text-sm">
        <thead className="border-b text-left text-muted-foreground">
          <tr>
            <th scope="col" className="px-4 py-2 font-medium">
              Fonte pagadora
            </th>
            {comIr && (
              <>
                <th scope="col" className="px-4 py-2 text-right font-medium">
                  Bruto
                </th>
                <th scope="col" className="px-4 py-2 text-right font-medium">
                  IR na fonte (15%)
                </th>
              </>
            )}
            <th scope="col" className="px-4 py-2 text-right font-medium">
              {comIr ? "Líquido (vai na ficha)" : "Valor"}
            </th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {itens.map((r) => (
            <tr key={r.ticker}>
              <td className="px-4 py-2">
                <span className="font-medium">{r.ticker}</span> <span className="text-muted-foreground">{r.nome}</span>
              </td>
              {comIr && (
                <>
                  <td className="whitespace-nowrap px-4 py-2 text-right tabular-nums">{formatarPreco(r.bruto)}</td>
                  <td className="whitespace-nowrap px-4 py-2 text-right tabular-nums">{formatarPreco(r.ir)}</td>
                </>
              )}
              <td className="whitespace-nowrap px-4 py-2 text-right font-medium tabular-nums">{formatarPreco(r.liquido)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot className="border-t">
          <tr>
            <th scope="row" className="px-4 py-2 text-left font-medium">
              Total
            </th>
            {comIr && (
              <>
                <td className="whitespace-nowrap px-4 py-2 text-right tabular-nums">{formatarPreco(soma(itens, "bruto"))}</td>
                <td className="whitespace-nowrap px-4 py-2 text-right tabular-nums">{formatarPreco(soma(itens, "ir"))}</td>
              </>
            )}
            <td className="whitespace-nowrap px-4 py-2 text-right font-semibold tabular-nums">{formatarPreco(soma(itens, "liquido"))}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

export default async function PaginaDeclaracao({ searchParams }: Props) {
  if (!(await auth())?.user) redirect("/entrar?voltar=/carteira");
  const lista = await ler<Carteiras>("/v1/carteiras");
  if (!lista || lista.itens.length === 0) redirect("/carteira");
  const params = await searchParams;
  const pedida = Number(params.c);
  const carteira = Number.isInteger(pedida) && pedida > 0 ? lista.itens.find((c) => c.id === pedida) : lista.itens[0];
  if (!carteira) notFound();
  const ano = Number(params.ano);
  const qs = Number.isInteger(ano) && ano >= 2000 && ano <= 2100 ? `?ano=${ano}` : "";
  const d = await ler<DeclaracaoCarteira>(`/v1/carteiras/${carteira.id}/declaracao${qs}`);

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-10">
      <div className="grid gap-4">
        <div>
          <Link href={`/carteira?c=${carteira.id}`} className="text-sm text-muted-foreground hover:text-foreground">
            Voltar para {carteira.nome}
          </Link>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">Declaração anual{d ? ` de ${d.ano}` : ""}</h1>
          <p className="mt-1 max-w-2xl text-muted-foreground">
            O que a carteira {carteira.nome} tem para cada ficha do programa do Imposto de Renda, com base nas operações e nos proventos lançados.
          </p>
        </div>
        {d && d.anos.length > 0 && (
          <nav aria-label="Ano-calendário" className="flex flex-wrap gap-2">
            {d.anos.map((a) => (
              <Button key={a} asChild size="sm" variant={a === d.ano ? "default" : "outline"}>
                <Link href={`/carteira/declaracao?c=${carteira.id}&ano=${a}`} aria-current={a === d.ano ? "page" : undefined}>
                  {a}
                </Link>
              </Button>
            ))}
          </nav>
        )}
      </div>

      {!d ? (
        <p role="alert" className="text-sm text-destructive">
          Não foi possível montar a declaração agora. Tente de novo em instantes.
        </p>
      ) : (
        <>
          <Ficha
            titulo="Bens e Direitos"
            termo="bens_direitos"
            onde={`Um item por ativo, com a situação em 31/12/${d.ano - 1} e em 31/12/${d.ano} pelo custo de aquisição (preço médio), não pelo valor de mercado.`}
          >
            {d.bens.length === 0 ? (
              <p className="rounded-xl border bg-card p-4 text-sm text-muted-foreground">
                Nenhuma posição em 31/12/{d.ano - 1} nem em 31/12/{d.ano}. Ativos comprados e vendidos dentro do mesmo ano não entram nesta ficha.
              </p>
            ) : (
              <ul className="grid gap-3">
                {d.bens.map((b) => (
                  <li key={b.ticker} className="grid gap-3 rounded-xl border bg-card p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold">
                          {b.ticker} <span className="font-normal text-muted-foreground">{b.nome}</span>
                        </p>
                        <p className="text-sm text-muted-foreground">
                          {b.grupo ? `Grupo ${b.grupo}, código ${b.codigo}: ` : ""}
                          {b.descricao_grupo}
                          {!b.grupo && " (confira o grupo e o código no programa)"}
                        </p>
                      </div>
                      <dl className="grid grid-cols-2 gap-x-6 text-sm">
                        <dt className="text-muted-foreground">31/12/{d.ano - 1}</dt>
                        <dt className="text-muted-foreground">31/12/{d.ano}</dt>
                        <dd className="font-medium tabular-nums">{formatarPreco(b.custo_anterior)}</dd>
                        <dd className="font-medium tabular-nums">{formatarPreco(b.custo)}</dd>
                        <dd className="text-xs text-muted-foreground tabular-nums">{qtd(b.quantidade_anterior)} un.</dd>
                        <dd className="text-xs text-muted-foreground tabular-nums">{qtd(b.quantidade)} un.</dd>
                      </dl>
                    </div>
                    <div className="flex flex-wrap items-center gap-3 rounded-lg bg-muted px-3 py-2">
                      <p className="min-w-0 flex-1 text-sm">{b.discriminacao}</p>
                      <Copiar texto={b.discriminacao} rotulo="Copiar discriminação" />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Ficha>

          <Ficha titulo="Rendimentos Isentos e Não Tributáveis" onde="Dividendos, rendimentos de FII e ganhos com ações em meses de vendas até R$ 20 mil.">
            <div className="grid gap-6">
              <div className="grid gap-2">
                <h3 className="font-medium">
                  <Termo termo="dividendos">Dividendos</Termo>
                </h3>
                <TabelaRendimentos itens={d.dividendos} vazio={`Nenhum dividendo pago em ${d.ano}.`} />
              </div>
              <div className="grid gap-2">
                <h3 className="font-medium">Rendimentos de fundos imobiliários</h3>
                <TabelaRendimentos itens={d.rendimentos_fii} vazio={`Nenhum rendimento de FII pago em ${d.ano}.`} />
              </div>
              <div className="grid gap-2 rounded-xl border bg-card p-4">
                <h3 className="font-medium">
                  <Termo termo="isencao_20mil">Ganhos líquidos em operações com ações até R$ 20 mil no mês</Termo>
                </h3>
                <p className="font-display text-2xl font-semibold tabular-nums">{formatarPreco(d.ganho_isento_acoes)}</p>
                <p className="text-sm text-muted-foreground">Soma dos ganhos com ações nos meses em que as vendas de ações não passaram de R$ 20 mil.</p>
              </div>
            </div>
          </Ficha>

          <Ficha titulo="Rendimentos Sujeitos à Tributação Exclusiva/Definitiva" termo="jcp" onde="Juros sobre capital próprio: o imposto de 15% já foi retido pela empresa; a ficha leva o valor líquido.">
            <TabelaRendimentos itens={d.jcp} comIr vazio={`Nenhum JCP pago em ${d.ano}.`} />
          </Ficha>

          <Ficha titulo="Renda Variável" onde="Operações comuns e day trade, mês a mês, com os DARFs pagos.">
            <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border bg-card p-4">
              <p className="text-sm">
                {d.meses_com_venda === 0 ? (
                  `Nenhuma venda em ${d.ano}: a ficha fica em branco.`
                ) : (
                  <>
                    {d.meses_com_venda === 1 ? "1 mês com venda" : `${d.meses_com_venda} meses com venda`} em {d.ano}, com DARFs de{" "}
                    <span className="font-medium tabular-nums">{formatarPreco(d.darfs)}</span>.
                  </>
                )}
              </p>
              {d.meses_com_venda > 0 && (
                <Button asChild variant="outline" size="sm">
                  <Link href={`/carteira/imposto?c=${carteira.id}`}>Ver mês a mês</Link>
                </Button>
              )}
            </div>
          </Ficha>

          <p className={cn("text-xs text-muted-foreground")}>{d.aviso}</p>
        </>
      )}
    </div>
  );
}

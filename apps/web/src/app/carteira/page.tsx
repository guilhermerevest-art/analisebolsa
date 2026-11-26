import { Trash2 } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { auth } from "@/auth";
import { BarrasAlocacao } from "@/components/carteira/alocacao";
import { FormularioOperacao } from "@/components/carteira/formulario-operacao";
import { GraficoRentabilidadeCliente } from "@/components/carteira/grafico-rentabilidade-cliente";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { criarCarteira, excluirCarteira, removerOperacao, renomearCarteira } from "@/lib/acoes-carteira";
import { chamarApi } from "@/lib/api";
import { classeVariacao, formatarData, formatarNumero, formatarPct, formatarPreco, NOMES_PROVENTO } from "@/lib/formato";
import type { Carteiras, Operacoes, RentabilidadeCarteira, ResumoCarteira } from "@/lib/tipos-api";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Minha carteira", robots: { index: false } };
export const dynamic = "force-dynamic";

type Props = { searchParams: Promise<{ c?: string; importadas?: string }> };

async function ler<T>(caminho: string): Promise<T | null> {
  const resp = await chamarApi(caminho, { cache: "no-store" });
  if (resp.status === 401) redirect("/entrar?voltar=/carteira");
  if (!resp.ok) return null;
  return (await resp.json()) as T;
}

const qtd = (v: string) => formatarNumero(v, Number.isInteger(Number(v)) ? 0 : 4);

function Valor({ rotulo, valor, classe, detalhe }: { rotulo: string; valor: string; classe?: string; detalhe?: string }) {
  return (
    <div className="rounded-lg border p-4">
      <dt className="text-sm text-muted-foreground">{rotulo}</dt>
      <dd className={cn("mt-1 text-xl font-semibold tabular-nums", classe)}>{valor}</dd>
      {detalhe && <dd className="text-xs text-muted-foreground">{detalhe}</dd>}
    </div>
  );
}

function NovaCarteira({ primeira }: { primeira: boolean }) {
  return (
    <form action={criarCarteira} className="flex gap-2">
      <label htmlFor="nome-carteira" className="sr-only">
        Nome da carteira
      </label>
      <Input id="nome-carteira" name="nome" placeholder={primeira ? "Minha carteira" : "Nome da nova carteira"} maxLength={60} className="max-w-56" />
      <Button type="submit" variant={primeira ? "default" : "outline"}>
        {primeira ? "Criar carteira" : "Nova carteira"}
      </Button>
    </form>
  );
}

export default async function PaginaCarteira({ searchParams }: Props) {
  if (!(await auth())?.user) redirect("/entrar?voltar=/carteira");
  const lista = await ler<Carteiras>("/v1/carteiras");
  if (!lista) {
    return (
      <p role="alert" className="text-sm text-destructive">
        Não foi possível carregar suas carteiras agora. Tente de novo em instantes.
      </p>
    );
  }

  if (lista.itens.length === 0) {
    return (
      <Card className="mx-auto w-full max-w-lg">
        <CardHeader>
          <CardTitle className="text-2xl">Minha carteira</CardTitle>
          <CardDescription>
            Lance suas compras e vendas para acompanhar posições, preço médio, proventos recebidos e alocação.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <NovaCarteira primeira />
        </CardContent>
      </Card>
    );
  }

  const params = await searchParams;
  const pedida = Number(params.c);
  const importadas = Number(params.importadas);
  const atual = lista.itens.find((c) => c.id === pedida) ?? lista.itens[0];
  const [resumo, ops, rent] = await Promise.all([
    ler<ResumoCarteira>(`/v1/carteiras/${atual.id}/resumo`),
    ler<Operacoes>(`/v1/carteiras/${atual.id}/operacoes`),
    ler<RentabilidadeCarteira>(`/v1/carteiras/${atual.id}/rentabilidade`),
  ]);
  // Tabela da rentabilidade: o último ponto de cada mês.
  const mensal = (rent?.pontos ?? []).filter((p, i, todos) => todos[i + 1]?.data.slice(0, 7) !== p.data.slice(0, 7)).reverse();
  const hoje = new Date().toLocaleDateString("sv-SE", { timeZone: "America/Sao_Paulo" });
  const t = resumo?.totais;
  const variacaoTotal = t && Number(t.custo) > 0 ? ((Number(t.patrimonio) - Number(t.custo)) / Number(t.custo)) * 100 : null;

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{atual.nome}</h1>
          <p className="mt-1 text-muted-foreground">Posições pelo último fechamento. Preço médio pelo método da Receita.</p>
        </div>
        {lista.itens.length < lista.limite && <NovaCarteira primeira={false} />}
      </div>

      {Number.isInteger(importadas) && importadas > 0 && (
        <p role="status" className="rounded-lg bg-positivo/10 px-4 py-3 text-sm text-positivo">
          {importadas === 1 ? "1 operação importada da B3." : `${importadas} operações importadas da B3.`} Corretagem e taxas entraram como zero.
        </p>
      )}

      {lista.itens.length > 1 && (
        <nav aria-label="Carteiras" className="flex flex-wrap gap-2">
          {lista.itens.map((c) => (
            <Button key={c.id} asChild size="sm" variant={c.id === atual.id ? "default" : "outline"}>
              <Link href={`/carteira?c=${c.id}`} aria-current={c.id === atual.id ? "page" : undefined}>
                {c.nome}
              </Link>
            </Button>
          ))}
        </nav>
      )}

      {!resumo || !ops ? (
        <p role="alert" className="text-sm text-destructive">
          Não foi possível carregar a carteira agora. Tente de novo em instantes.
        </p>
      ) : (
        <>
          {t && resumo.posicoes.length + ops.itens.length > 0 && (
            <dl className="grid grid-cols-2 gap-3 lg:grid-cols-5">
              <Valor rotulo="Patrimônio" valor={formatarPreco(t.patrimonio)} />
              <Valor rotulo="Custo das posições" valor={formatarPreco(t.custo)} />
              <Valor
                rotulo="Resultado em aberto"
                valor={formatarPreco(t.resultado_nao_realizado)}
                classe={classeVariacao(Number(t.resultado_nao_realizado))}
                detalhe={variacaoTotal === null ? undefined : `${formatarPct(variacaoTotal)} sobre o custo`}
              />
              <Valor rotulo="Resultado realizado" valor={formatarPreco(t.resultado_realizado)} classe={classeVariacao(Number(t.resultado_realizado))} detalhe="Nas vendas" />
              <Valor rotulo="Proventos recebidos" valor={formatarPreco(t.proventos)} detalhe="Valor bruto" />
            </dl>
          )}

          {rent && rent.pontos.length > 1 && (
            <section aria-labelledby="titulo-rentabilidade" className="grid gap-3">
              <div>
                <h2 id="titulo-rentabilidade" className="text-xl font-semibold">
                  Rentabilidade
                </h2>
                <p className="text-sm text-muted-foreground">
                  Retorno acumulado desde {formatarData(rent.inicio)}, ponderado pelo tempo (aportes e retiradas não distorcem), com proventos. CDI e Ibovespa no mesmo período.
                </p>
              </div>
              <div className="rounded-lg border p-4">
                <GraficoRentabilidadeCliente dados={rent} />
              </div>
              <details className="text-sm">
                <summary className="cursor-pointer text-muted-foreground">Ver em tabela (fim de cada mês)</summary>
                <div className="relative mt-2 max-h-80 overflow-auto">
                  <table className="w-full">
                    <thead className="sticky top-0 bg-background text-muted-foreground">
                      <tr>
                        <th scope="col" className="py-2 text-left font-normal">Data</th>
                        <th scope="col" className="py-2 pl-3 text-right font-normal">Patrimônio</th>
                        <th scope="col" className="py-2 pl-3 text-right font-normal">Carteira</th>
                        <th scope="col" className="py-2 pl-3 text-right font-normal">CDI</th>
                        <th scope="col" className="py-2 pl-3 text-right font-normal">Ibovespa</th>
                      </tr>
                    </thead>
                    <tbody>
                      {mensal.map((p) => (
                        <tr key={p.data} className="border-t">
                          <td className="py-1.5 tabular-nums">{formatarData(p.data)}</td>
                          <td className="py-1.5 pl-3 text-right tabular-nums">{formatarPreco(p.patrimonio)}</td>
                          <td className="py-1.5 pl-3 text-right tabular-nums">{formatarPct(p.carteira)}</td>
                          <td className="py-1.5 pl-3 text-right tabular-nums">{formatarPct(p.cdi)}</td>
                          <td className="py-1.5 pl-3 text-right tabular-nums">{formatarPct(p.ibov)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
              <p className="text-xs text-muted-foreground">Rentabilidade passada não garante resultado futuro.</p>
            </section>
          )}

          <section aria-labelledby="titulo-posicoes" className="grid gap-3">
            <h2 id="titulo-posicoes" className="text-xl font-semibold">
              Posições
            </h2>
            {resumo.posicoes.length === 0 ? (
              <p className="text-sm text-muted-foreground">Nenhuma posição em aberto. Lance uma compra abaixo.</p>
            ) : (
              <div className="relative overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-muted-foreground">
                    <tr>
                      <th scope="col" className="py-2 text-left font-normal">Ativo</th>
                      <th scope="col" className="py-2 pl-3 text-right font-normal">Quantidade</th>
                      <th scope="col" className="py-2 pl-3 text-right font-normal">Preço médio</th>
                      <th scope="col" className="py-2 pl-3 text-right font-normal">Último</th>
                      <th scope="col" className="py-2 pl-3 text-right font-normal">Valor</th>
                      <th scope="col" className="py-2 pl-3 text-right font-normal">Resultado</th>
                      <th scope="col" className="hidden py-2 pl-3 text-right font-normal sm:table-cell">Proventos</th>
                    </tr>
                  </thead>
                  <tbody>
                    {resumo.posicoes.map((p) => (
                      <tr key={p.ticker} className="border-t">
                        <td className="py-2 pr-3">
                          <Link href={`/ativo/${p.ticker}`} className="font-semibold hover:underline">
                            {p.ticker}
                          </Link>
                          <span className="block max-w-48 truncate text-xs text-muted-foreground">{p.nome}</span>
                        </td>
                        <td className="whitespace-nowrap py-2 pl-3 text-right tabular-nums">{qtd(p.quantidade)}</td>
                        <td className="whitespace-nowrap py-2 pl-3 text-right tabular-nums">{formatarPreco(p.preco_medio)}</td>
                        <td className="whitespace-nowrap py-2 pl-3 text-right tabular-nums" title={p.data_preco ? `Fechamento de ${formatarData(p.data_preco)}` : "Sem cotação"}>
                          {formatarPreco(p.preco_atual)}
                        </td>
                        <td className="whitespace-nowrap py-2 pl-3 text-right tabular-nums">{formatarPreco(p.valor_atual)}</td>
                        <td className={cn("whitespace-nowrap py-2 pl-3 text-right tabular-nums", classeVariacao(p.variacao))}>
                          {formatarPreco(p.resultado)}
                          <span className="block text-xs">{formatarPct(p.variacao)}</span>
                        </td>
                        <td className="hidden whitespace-nowrap py-2 pl-3 text-right tabular-nums sm:table-cell">{formatarPreco(p.proventos)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {resumo.posicoes.length > 0 && (
            <section aria-labelledby="titulo-alocacao" className="grid gap-3">
              <h2 id="titulo-alocacao" className="text-xl font-semibold">
                Alocação
              </h2>
              <div className="grid gap-6 rounded-lg border p-4 sm:grid-cols-3">
                <BarrasAlocacao titulo="Ativo" fatias={resumo.alocacao.ativo} />
                <BarrasAlocacao titulo="Setor" fatias={resumo.alocacao.setor} />
                <BarrasAlocacao titulo="Tipo" fatias={resumo.alocacao.tipo} />
              </div>
            </section>
          )}

          <section aria-labelledby="titulo-lancar" className="grid gap-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 id="titulo-lancar" className="text-xl font-semibold">
                Lançar operação
              </h2>
              <Button asChild variant="outline" size="sm">
                <Link href={`/carteira/importar?c=${atual.id}`}>Importar da B3</Link>
              </Button>
            </div>
            <div className="rounded-lg border p-4">
              <FormularioOperacao carteira={atual.id} hoje={hoje} />
            </div>
          </section>

          {ops.itens.length > 0 && (
            <section aria-labelledby="titulo-operacoes" className="grid gap-3">
              <h2 id="titulo-operacoes" className="text-xl font-semibold">
                Operações
              </h2>
              <div className="relative overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-muted-foreground">
                    <tr>
                      <th scope="col" className="py-2 text-left font-normal">Data</th>
                      <th scope="col" className="py-2 pl-3 text-left font-normal">Ativo</th>
                      <th scope="col" className="py-2 pl-3 text-left font-normal">Tipo</th>
                      <th scope="col" className="py-2 pl-3 text-right font-normal">Quantidade</th>
                      <th scope="col" className="py-2 pl-3 text-right font-normal">Preço</th>
                      <th scope="col" className="hidden py-2 pl-3 text-right font-normal sm:table-cell">Custos</th>
                      <th scope="col" className="w-10">
                        <span className="sr-only">Excluir</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {ops.itens.map((o) => (
                      <tr key={o.id} className="border-t">
                        <td className="whitespace-nowrap py-2 tabular-nums">{formatarData(o.data)}</td>
                        <td className="py-2 pl-3 font-medium">{o.ticker}</td>
                        <td className={cn("py-2 pl-3", o.tipo === "venda" && "text-muted-foreground")}>{o.tipo === "compra" ? "Compra" : "Venda"}</td>
                        <td className="whitespace-nowrap py-2 pl-3 text-right tabular-nums">{qtd(o.quantidade)}</td>
                        <td className="whitespace-nowrap py-2 pl-3 text-right tabular-nums">{formatarPreco(o.preco)}</td>
                        <td className="hidden whitespace-nowrap py-2 pl-3 text-right tabular-nums sm:table-cell">{formatarPreco(o.custos)}</td>
                        <td className="py-1 pl-2 text-right">
                          <form action={removerOperacao}>
                            <input type="hidden" name="carteira" value={atual.id} />
                            <input type="hidden" name="operacao" value={o.id} />
                            <Button type="submit" variant="ghost" size="icon" className="size-8" title="Excluir operação">
                              <Trash2 aria-hidden />
                              <span className="sr-only">
                                Excluir {o.tipo} de {o.ticker} em {formatarData(o.data)}
                              </span>
                            </Button>
                          </form>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="text-xs text-muted-foreground">Uma operação que deixaria uma venda posterior sem posição não pode ser excluída.</p>
            </section>
          )}

          {resumo.proventos.length > 0 && (
            <section aria-labelledby="titulo-proventos" className="grid gap-3">
              <h2 id="titulo-proventos" className="text-xl font-semibold">
                Proventos recebidos
              </h2>
              <div className="relative overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-muted-foreground">
                    <tr>
                      <th scope="col" className="py-2 text-left font-normal">Data com</th>
                      <th scope="col" className="py-2 pl-3 text-left font-normal">Ativo</th>
                      <th scope="col" className="py-2 pl-3 text-left font-normal">Tipo</th>
                      <th scope="col" className="hidden py-2 pl-3 text-right font-normal sm:table-cell">Por cota</th>
                      <th scope="col" className="hidden py-2 pl-3 text-right font-normal sm:table-cell">Cotas</th>
                      <th scope="col" className="py-2 pl-3 text-right font-normal">Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {resumo.proventos.slice(0, 50).map((p) => (
                      <tr key={`${p.ticker}-${p.tipo}-${p.data_com}`} className="border-t">
                        <td className="whitespace-nowrap py-2 tabular-nums">{formatarData(p.data_com)}</td>
                        <td className="py-2 pl-3 font-medium">{p.ticker}</td>
                        <td className="py-2 pl-3">{NOMES_PROVENTO[p.tipo] ?? p.tipo}</td>
                        <td className="hidden whitespace-nowrap py-2 pl-3 text-right tabular-nums sm:table-cell">{formatarPreco(p.valor_unitario)}</td>
                        <td className="hidden whitespace-nowrap py-2 pl-3 text-right tabular-nums sm:table-cell">{qtd(p.quantidade)}</td>
                        <td className="whitespace-nowrap py-2 pl-3 text-right tabular-nums">{formatarPreco(p.total)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="text-xs text-muted-foreground">Valores brutos, pela quantidade em carteira no fim da data com. JCP tem 15% de IR retido na fonte.</p>
            </section>
          )}

          <details className="rounded-lg border p-4 text-sm">
            <summary className="cursor-pointer font-medium">Gerenciar carteira</summary>
            <div className="mt-4 flex flex-wrap items-end gap-6">
              <form action={renomearCarteira} className="flex gap-2">
                <input type="hidden" name="carteira" value={atual.id} />
                <label htmlFor="renomear" className="sr-only">
                  Novo nome
                </label>
                <Input id="renomear" name="nome" defaultValue={atual.nome} maxLength={60} required className="max-w-56" />
                <Button type="submit" variant="outline">
                  Renomear
                </Button>
              </form>
              <form action={excluirCarteira}>
                <input type="hidden" name="carteira" value={atual.id} />
                <Button type="submit" variant="outline" className="text-destructive">
                  Excluir esta carteira e as {atual.operacoes} operações
                </Button>
              </form>
            </div>
          </details>
        </>
      )}
    </div>
  );
}

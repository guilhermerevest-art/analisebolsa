import { Pencil, Trash2 } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { auth } from "@/auth";
import { BarrasAlocacao } from "@/components/carteira/alocacao";
import { FormularioInvestimento } from "@/components/carteira/formulario-investimento";
import { FormularioOperacao } from "@/components/carteira/formulario-operacao";
import { GraficoRentabilidadeCliente } from "@/components/carteira/grafico-rentabilidade-cliente";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { criarCarteira, excluirCarteira, removerInvestimento, removerOperacao, renomearCarteira } from "@/lib/acoes-carteira";
import { chamarApi } from "@/lib/api";
import { classeVariacao, formatarData, formatarNumero, formatarPct, formatarPreco, NOMES_PROVENTO } from "@/lib/formato";
import type { Carteiras, InvestimentoCarteira, Investimentos, Operacoes, RentabilidadeCarteira, ResumoCarteira } from "@/lib/tipos-api";
import { cn } from "@/lib/utils";
import { Termo } from "@/components/dica";
import type { ChaveGlossario } from "@/lib/glossario";

export const metadata: Metadata = { title: "Minha carteira", robots: { index: false } };
export const dynamic = "force-dynamic";

type Props = { searchParams: Promise<{ c?: string; importadas?: string; editar?: string; editada?: string; investimento?: string }> };

async function ler<T>(caminho: string): Promise<T | null> {
  const resp = await chamarApi(caminho, { cache: "no-store" });
  if (resp.status === 401) redirect("/entrar?voltar=/carteira");
  if (!resp.ok) return null;
  return (await resp.json()) as T;
}

const qtd = (v: string) => formatarNumero(v, Number.isInteger(Number(v)) ? 0 : 4);

function Valor({ rotulo, valor, classe, detalhe, termo }: { rotulo: string; valor: string; classe?: string; detalhe?: string; termo?: ChaveGlossario }) {
  return (
    <div className="rounded-xl border bg-card p-4">
      <dt className="text-sm text-muted-foreground">{termo ? <Termo termo={termo}>{rotulo}</Termo> : rotulo}</dt>
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
            Lance suas compras e vendas, CDBs, Tesouro e fundos para acompanhar posições, preço médio, proventos, rendimento e alocação.
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
  const editarId = Number(params.editar);
  const atual = lista.itens.find((c) => c.id === pedida) ?? lista.itens[0];
  const [resumo, ops, rent, invs] = await Promise.all([
    ler<ResumoCarteira>(`/v1/carteiras/${atual.id}/resumo`),
    ler<Operacoes>(`/v1/carteiras/${atual.id}/operacoes`),
    ler<RentabilidadeCarteira>(`/v1/carteiras/${atual.id}/rentabilidade`),
    ler<Investimentos>(`/v1/carteiras/${atual.id}/investimentos`),
  ]);
  const invEmEdicao = invs?.itens.find((i) => i.id === Number(params.investimento));
  // Tabela da rentabilidade: o último ponto de cada mês.
  const mensal = (rent?.pontos ?? []).filter((p, i, todos) => todos[i + 1]?.data.slice(0, 7) !== p.data.slice(0, 7)).reverse();
  const hoje = new Date().toLocaleDateString("sv-SE", { timeZone: "America/Sao_Paulo" });
  const t = resumo?.totais;
  const emEdicao = Number.isInteger(editarId) ? ops?.itens.find((o) => o.id === editarId) : undefined;
  const variacaoTotal = t && Number(t.custo) > 0 ? ((Number(t.patrimonio) - Number(t.custo)) / Number(t.custo)) * 100 : null;

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">{atual.nome}</h1>
          <p className="mt-1 text-muted-foreground">Posições pelo último fechamento. Preço médio pelo método da Receita.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button asChild variant="outline">
            <Link href={`/carteira/imposto?c=${atual.id}`}>Imposto de renda</Link>
          </Button>
          <Button asChild variant="outline">
            <Link href={`/carteira/declaracao?c=${atual.id}`}>Declaração anual</Link>
          </Button>
          {lista.itens.length < lista.limite && <NovaCarteira primeira={false} />}
        </div>
      </div>

      {Number.isInteger(importadas) && importadas > 0 && (
        <p role="status" className="rounded-lg bg-positivo/10 px-4 py-3 text-sm text-positivo">
          {importadas === 1 ? "1 operação importada da B3." : `${importadas} operações importadas da B3.`} Corretagem e taxas entraram como zero:
          use o lápis ao lado de cada operação para incluir.
        </p>
      )}

      {params.editada === "1" && (
        <p role="status" className="rounded-lg bg-positivo/10 px-4 py-3 text-sm text-positivo">
          Operação salva.
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
              <Valor rotulo="Custo das posições" termo="preco_medio" valor={formatarPreco(t.custo)} />
              <Valor
                rotulo="Resultado em aberto"
                termo="resultado_aberto"
                valor={formatarPreco(t.resultado_nao_realizado)}
                classe={classeVariacao(Number(t.resultado_nao_realizado))}
                detalhe={variacaoTotal === null ? undefined : `${formatarPct(variacaoTotal)} sobre o custo`}
              />
              <Valor rotulo="Resultado realizado" termo="resultado_realizado" valor={formatarPreco(t.resultado_realizado)} classe={classeVariacao(Number(t.resultado_realizado))} detalhe="Nas vendas" />
              <Valor rotulo="Proventos recebidos" termo="proventos" valor={formatarPreco(t.proventos)} detalhe="Valor bruto" />
            </dl>
          )}

          {rent && rent.pontos.length > 1 && (
            <section aria-labelledby="titulo-rentabilidade" className="grid gap-3">
              <div>
                <h2 id="titulo-rentabilidade" className="text-xl font-semibold">
                  <Termo termo="rentabilidade_twr">Rentabilidade</Termo>
                </h2>
                <p className="text-sm text-muted-foreground">
                  Retorno acumulado desde {formatarData(rent.inicio)}, ponderado pelo tempo (aportes e retiradas não distorcem), com proventos. CDI, Ibovespa e dólar no mesmo período.
                </p>
              </div>
              <div className="rounded-xl border bg-card p-4">
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
                        <th scope="col" className="py-2 pl-3 text-right font-normal">Dólar</th>
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
                          <td className="py-1.5 pl-3 text-right tabular-nums">{formatarPct(p.dolar ?? null)}</td>
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
              <div className="grid gap-6 rounded-xl border bg-card p-4 sm:grid-cols-3">
                <BarrasAlocacao titulo="Ativo" fatias={resumo.alocacao.ativo} />
                <BarrasAlocacao titulo="Setor" fatias={resumo.alocacao.setor} />
                <BarrasAlocacao titulo="Tipo" fatias={resumo.alocacao.tipo} />
              </div>
            </section>
          )}

          {invs && <RendaFixa dados={invs} carteira={atual.id} hoje={hoje} emEdicao={invEmEdicao} patrimonioAcoes={t ? Number(t.patrimonio) : 0} />}

          <section id="lancar" aria-labelledby="titulo-lancar" className="grid scroll-mt-24 gap-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 id="titulo-lancar" className="text-xl font-semibold">
                {emEdicao ? `Editar operação de ${emEdicao.ticker} em ${formatarData(emEdicao.data)}` : "Lançar operação"}
              </h2>
              <Button asChild variant="outline" size="sm">
                <Link href={`/carteira/importar?c=${atual.id}`}>Importar da B3</Link>
              </Button>
            </div>
            <div className="rounded-xl border bg-card p-4">
              <FormularioOperacao key={emEdicao?.id ?? "nova"} carteira={atual.id} hoje={hoje} operacao={emEdicao} />
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
                      <th scope="col" className="w-20">
                        <span className="sr-only">Editar ou excluir</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {ops.itens.map((o) => (
                      <tr key={o.id} className={cn("border-t", o.id === emEdicao?.id && "bg-accent")}>
                        <td className="whitespace-nowrap py-2 tabular-nums">{formatarData(o.data)}</td>
                        <td className="py-2 pl-3 font-medium">{o.ticker}</td>
                        <td className={cn("py-2 pl-3", o.tipo === "venda" && "text-muted-foreground")}>{o.tipo === "compra" ? "Compra" : "Venda"}</td>
                        <td className="whitespace-nowrap py-2 pl-3 text-right tabular-nums">{qtd(o.quantidade)}</td>
                        <td className="whitespace-nowrap py-2 pl-3 text-right tabular-nums">{formatarPreco(o.preco)}</td>
                        <td className="hidden whitespace-nowrap py-2 pl-3 text-right tabular-nums sm:table-cell">{formatarPreco(o.custos)}</td>
                        <td className="flex justify-end gap-0.5 py-1 pl-2">
                          <Button asChild variant="ghost" size="icon" className="size-8" title="Editar operação">
                            <Link href={`/carteira?c=${atual.id}&editar=${o.id}#lancar`}>
                              <Pencil aria-hidden />
                              <span className="sr-only">
                                Editar {o.tipo} de {o.ticker} em {formatarData(o.data)}
                              </span>
                            </Link>
                          </Button>
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
              <p className="text-xs text-muted-foreground">Uma operação que deixaria uma venda posterior sem posição não pode ser alterada nem excluída.</p>
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

          <details className="rounded-xl border bg-card p-4 text-sm">
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

function RendaFixa({
  dados,
  carteira,
  hoje,
  emEdicao,
  patrimonioAcoes,
}: {
  dados: Investimentos;
  carteira: number;
  hoje: string;
  emEdicao?: InvestimentoCarteira;
  patrimonioAcoes: number;
}) {
  const { itens, totais } = dados;
  const abertos = itens.filter((i) => !i.resgate_data);
  const ganho = totais.liquido - totais.aplicado;
  return (
    <section id="renda-fixa" aria-labelledby="titulo-renda-fixa" className="grid scroll-mt-24 gap-3">
      <div>
        <h2 id="titulo-renda-fixa" className="text-xl font-semibold">
          <Termo termo="renda_fixa">Renda fixa</Termo> e <Termo termo="fundo_investimento">fundos</Termo>
        </h2>
        <p className="text-sm text-muted-foreground">CDBs, LCIs, Tesouro, debêntures e fundos, com o valor estimado de hoje e o imposto se resgatasse agora.</p>
      </div>

      {abertos.length > 0 && (
        <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Valor rotulo="Aplicado" valor={formatarPreco(totais.aplicado)} />
          <Valor rotulo="Valor bruto hoje" valor={formatarPreco(totais.bruto)} />
          <Valor
            rotulo="Líquido de IR"
            termo="ir_regressivo"
            valor={formatarPreco(totais.liquido)}
            classe={classeVariacao(ganho)}
            detalhe={totais.aplicado > 0 ? `${formatarPct((ganho / totais.aplicado) * 100)} sobre o aplicado` : undefined}
          />
          <Valor rotulo="Patrimônio total" valor={formatarPreco(patrimonioAcoes + totais.bruto)} detalhe="Bolsa + renda fixa e fundos" />
        </dl>
      )}

      {itens.length > 0 && (
        <div className="relative overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-muted-foreground">
              <tr>
                <th scope="col" className="py-2 text-left font-normal">Investimento</th>
                <th scope="col" className="hidden py-2 pl-3 text-left font-normal md:table-cell">Aplicação</th>
                <th scope="col" className="py-2 pl-3 text-right font-normal">Aplicado</th>
                <th scope="col" className="hidden py-2 pl-3 text-right font-normal sm:table-cell">Bruto</th>
                <th scope="col" className="hidden py-2 pl-3 text-right font-normal sm:table-cell">IR</th>
                <th scope="col" className="py-2 pl-3 text-right font-normal">Líquido</th>
                <th scope="col" className="w-20">
                  <span className="sr-only">Editar ou excluir</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {itens.map((i) => (
                <tr key={i.id} className={cn("border-t", i.id === emEdicao?.id && "bg-accent", i.resgate_data && "text-muted-foreground")}>
                  <td className="py-2 pr-3">
                    <span className="font-medium text-foreground">{i.nome}</span>
                    <span className="block text-xs text-muted-foreground">
                      {i.tipo_nome}
                      {i.descricao_taxa && ` · ${i.descricao_taxa}`}
                      {i.isento_ir && " · isento"}
                      {i.vencimento && ` · vence ${formatarData(i.vencimento)}`}
                      {i.resgate_data && ` · resgatado em ${formatarData(i.resgate_data)}`}
                    </span>
                  </td>
                  <td className="hidden whitespace-nowrap py-2 pl-3 tabular-nums md:table-cell">{formatarData(i.data_aplicacao)}</td>
                  <td className="whitespace-nowrap py-2 pl-3 text-right tabular-nums">{formatarPreco(i.valor_aplicado)}</td>
                  <td className="hidden whitespace-nowrap py-2 pl-3 text-right tabular-nums sm:table-cell" title={`Estimativa em ${formatarData(i.avaliado_em)}`}>
                    {formatarPreco(i.bruto)}
                  </td>
                  <td className="hidden whitespace-nowrap py-2 pl-3 text-right tabular-nums sm:table-cell">
                    {i.tipo === "fundo" ? (
                      <span className="text-xs text-muted-foreground">
                        <Termo termo="come_cotas">no fundo</Termo>
                      </span>
                    ) : (
                      <>
                        {formatarPreco(i.ir)}
                        {i.aliquota_ir ? <span className="block text-xs text-muted-foreground">{formatarNumero(i.aliquota_ir, 1)}%</span> : null}
                      </>
                    )}
                  </td>
                  <td className={cn("whitespace-nowrap py-2 pl-3 text-right tabular-nums", !i.resgate_data && classeVariacao(i.rendimento))}>
                    {i.bruto === null ? <span className="text-xs text-muted-foreground">{i.observacao}</span> : formatarPreco(i.liquido ?? i.bruto)}
                    {i.rendimento !== null && <span className="block text-xs">{formatarPct(i.rendimento)}</span>}
                  </td>
                  <td className="flex justify-end gap-0.5 py-1 pl-2">
                    <Button asChild variant="ghost" size="icon" className="size-8" title="Editar investimento">
                      <Link href={`/carteira?c=${carteira}&investimento=${i.id}#incluir-investimento`}>
                        <Pencil aria-hidden />
                        <span className="sr-only">Editar {i.nome}</span>
                      </Link>
                    </Button>
                    <form action={removerInvestimento}>
                      <input type="hidden" name="carteira" value={carteira} />
                      <input type="hidden" name="investimento" value={i.id} />
                      <Button type="submit" variant="ghost" size="icon" className="size-8" title="Excluir investimento">
                        <Trash2 aria-hidden />
                        <span className="sr-only">Excluir {i.nome}</span>
                      </Button>
                    </form>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div id="incluir-investimento" className="grid scroll-mt-24 gap-3 rounded-xl border bg-card p-4">
        <h3 className="font-medium">{emEdicao ? `Editar ${emEdicao.nome}` : "Incluir investimento"}</h3>
        <FormularioInvestimento key={emEdicao?.id ?? "novo"} carteira={carteira} hoje={hoje} investimento={emEdicao} />
      </div>
      {itens.length > 0 && (
        <p className="text-xs text-muted-foreground">
          Valores estimados pela regra de cada aplicação, sem taxas de custódia nem IOF (que só existe nos primeiros 30 dias). Fundos mostram o valor bruto, antes do
          come-cotas e do imposto no resgate.
        </p>
      )}
    </section>
  );
}

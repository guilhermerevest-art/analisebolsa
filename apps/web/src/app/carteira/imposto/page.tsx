import { Info } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { auth } from "@/auth";
import { chamarApi } from "@/lib/api";
import { classeVariacao, formatarData, formatarPreco } from "@/lib/formato";
import type { Carteiras, ImpostoCarteira } from "@/lib/tipos-api";
import { cn } from "@/lib/utils";
import { Termo } from "@/components/dica";
import type { ChaveGlossario } from "@/lib/glossario";

export const metadata: Metadata = { title: "Imposto de renda", robots: { index: false } };
export const dynamic = "force-dynamic";

type Props = { searchParams: Promise<{ c?: string }> };
type Mes = ImpostoCarteira["meses"][number];

async function ler<T>(caminho: string): Promise<T | null> {
  const resp = await chamarApi(caminho, { cache: "no-store" });
  if (resp.status === 401) redirect("/entrar?voltar=/carteira");
  return resp.ok ? ((await resp.json()) as T) : null;
}

function nomeMes(iso: string): string {
  const [a, m] = iso.split("-").map(Number);
  const nome = new Date(Date.UTC(a, m - 1, 15)).toLocaleDateString("pt-BR", { month: "long", timeZone: "UTC" });
  return `${nome.charAt(0).toUpperCase()}${nome.slice(1)} de ${a}`;
}

const n = (v: string) => Number(v);

function Cartao({ rotulo, valor, detalhe, destaque, termo }: { rotulo: string; valor: string; detalhe?: string; destaque?: boolean; termo?: ChaveGlossario }) {
  return (
    <div className={cn("grid content-start gap-1 rounded-xl border p-4", destaque ? "border-transparent bg-safira text-white" : "bg-card")}>
      <dt className={cn("text-sm", destaque ? "text-white [&_button]:text-white" : "text-muted-foreground")}>
        {termo ? <Termo termo={termo}>{rotulo}</Termo> : rotulo}
      </dt>
      <dd className="font-display text-2xl font-semibold tracking-tight tabular-nums">{valor}</dd>
      {detalhe && <dd className={cn("text-xs", destaque ? "text-white" : "text-muted-foreground")}>{detalhe}</dd>}
    </div>
  );
}

function Resultado({ v }: { v: string }) {
  return n(v) === 0 ? <span className="text-muted-foreground">—</span> : <span className={cn("whitespace-nowrap", classeVariacao(n(v)))}>{formatarPreco(v)}</span>;
}

function situacao(m: Mes): string {
  const partes: string[] = [];
  if (n(m.ganho_isento) > 0) partes.push("Ganho em ações isento (vendas até R$ 20 mil)");
  const prejuizo = [m.resultado_acoes, m.resultado_etf_bdr, m.resultado_fii, m.resultado_day_trade].filter((v) => n(v) < 0).reduce((t, v) => t - n(v), 0);
  if (prejuizo > 0) partes.push(`Prejuízo de ${formatarPreco(prejuizo)} fica para compensar`);
  if (n(m.darf) > 0) partes.push(`DARF vence em ${formatarData(m.vencimento)}`);
  else if (n(m.fica_para_depois) > 0) partes.push(`${formatarPreco(m.fica_para_depois)} abaixo do mínimo de R$ 10 passa para o mês seguinte`);
  else if (n(m.imposto_devido) > 0) partes.push("Imposto coberto pelo IRRF");
  return partes.length ? `${partes.join(". ")}.` : "Sem imposto no mês.";
}

export default async function PaginaImposto({ searchParams }: Props) {
  if (!(await auth())?.user) redirect("/entrar?voltar=/carteira");
  const lista = await ler<Carteiras>("/v1/carteiras");
  if (!lista || lista.itens.length === 0) redirect("/carteira");
  const pedida = Number((await searchParams).c);
  const carteira = Number.isInteger(pedida) && pedida > 0 ? lista.itens.find((c) => c.id === pedida) : lista.itens[0];
  if (!carteira) notFound();
  const dados = await ler<ImpostoCarteira>(`/v1/carteiras/${carteira.id}/imposto`);

  const hoje = new Date().toLocaleDateString("sv-SE", { timeZone: "America/Sao_Paulo" });
  const proximo = dados?.meses.filter((m) => n(m.darf) > 0 && m.vencimento && m.vencimento >= hoje).at(-1);
  const anoAtual = dados?.anos[0];

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-8">
      <div>
        <Link href={`/carteira?c=${carteira.id}`} className="text-sm text-muted-foreground hover:text-foreground">
          Voltar para {carteira.nome}
        </Link>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">Imposto de renda</h1>
        <p className="mt-1 max-w-2xl text-muted-foreground">
          Apuração mês a mês das vendas da carteira {carteira.nome}: ações, ETFs e BDRs a 15%, FIIs a 20% e day trade a 20%, com a isenção de
          vendas de ações até R$ 20 mil no mês e a compensação de prejuízos.
        </p>
      </div>

      {!dados ? (
        <p role="alert" className="text-sm text-destructive">
          Não foi possível calcular agora. Tente de novo em instantes.
        </p>
      ) : dados.meses.length === 0 ? (
        <div className="rounded-xl border bg-card p-6">
          <p className="font-medium">Nenhuma venda lançada ainda.</p>
          <p className="mt-1 text-sm text-muted-foreground">O imposto só aparece nos meses com venda. Lance as operações ou importe o extrato da B3.</p>
        </div>
      ) : (
        <>
          <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Cartao
              destaque
              termo="darf"
              rotulo="Próximo DARF"
              valor={proximo ? formatarPreco(proximo.darf) : "Nada a pagar"}
              detalhe={proximo ? `Vence em ${formatarData(proximo.vencimento)}, código ${dados.codigo_darf}` : "Nenhum DARF com vencimento pela frente"}
            />
            <Cartao
              rotulo="Prejuízo a compensar"
              termo="prejuizo_compensar"
              valor={formatarPreco(String(n(dados.prejuizo_comum) + n(dados.prejuizo_fii) + n(dados.prejuizo_day_trade)))}
              detalhe={`Ações, ETFs e BDRs: ${formatarPreco(dados.prejuizo_comum)}. FIIs: ${formatarPreco(dados.prejuizo_fii)}. Day trade: ${formatarPreco(dados.prejuizo_day_trade)}.`}
            />
            {anoAtual && (
              <Cartao rotulo={`Ganhos isentos em ${anoAtual.ano}`} termo="isencao_20mil" valor={formatarPreco(anoAtual.ganho_isento)} detalhe="Ações em meses com vendas até R$ 20 mil" />
            )}
            <Cartao
              rotulo="Para os próximos meses"
              termo="irrf"
              valor={formatarPreco(String(n(dados.pendente) + n(dados.saldo_irrf)))}
              detalhe={`Imposto abaixo de R$ 10 a somar: ${formatarPreco(dados.pendente)}. IRRF a descontar: ${formatarPreco(dados.saldo_irrf)}.`}
            />
          </dl>

          {dados.day_trade.length > 0 && (
            <div role="note" className="flex gap-3 rounded-xl border bg-card p-4 text-sm">
              <Info aria-hidden className="mt-0.5 size-4 shrink-0 text-azul" />
              <div className="grid gap-1">
                <p className="font-medium">Day trade</p>
                <p className="text-muted-foreground">
                  Compra e venda do mesmo ativo no mesmo dia foram apuradas como day trade (20%, sem isenção e com prejuízo separado), como se
                  tivessem sido na mesma corretora. Se foram em corretoras diferentes, não é day trade: lance cada corretora numa carteira. Dias
                  apurados assim: {dados.day_trade.map((d) => `${d.ticker} em ${formatarData(d.data)}`).join(", ")}.
                </p>
              </div>
            </div>
          )}

          <section aria-labelledby="titulo-meses" className="grid gap-3">
            <h2 id="titulo-meses" className="text-xl font-semibold">
              Mês a mês
            </h2>

            <ul className="grid gap-3 lg:hidden">
              {dados.meses.map((m) => (
                <li key={m.mes} className="grid gap-3 rounded-xl border bg-card p-4 text-sm">
                  <div className="flex items-baseline justify-between gap-3">
                    <h3 className="font-semibold">{nomeMes(m.mes)}</h3>
                    <span className="font-display text-lg font-semibold tabular-nums">{n(m.darf) > 0 ? formatarPreco(m.darf) : "—"}</span>
                  </div>
                  <p className="text-muted-foreground">{situacao(m)}</p>
                  <dl className="grid grid-cols-2 gap-x-4 gap-y-1">
                    <dt className="text-muted-foreground">Vendas de ações</dt>
                    <dd className="text-right tabular-nums">{formatarPreco(m.vendas_acoes)}</dd>
                    <dt className="text-muted-foreground">Ações</dt>
                    <dd className="text-right tabular-nums">
                      <Resultado v={m.resultado_acoes} />
                    </dd>
                    <dt className="text-muted-foreground">ETFs e BDRs</dt>
                    <dd className="text-right tabular-nums">
                      <Resultado v={m.resultado_etf_bdr} />
                    </dd>
                    <dt className="text-muted-foreground">FIIs</dt>
                    <dd className="text-right tabular-nums">
                      <Resultado v={m.resultado_fii} />
                    </dd>
                    <dt className="text-muted-foreground">Day trade</dt>
                    <dd className="text-right tabular-nums">
                      <Resultado v={m.resultado_day_trade} />
                    </dd>
                    <dt className="text-muted-foreground">Imposto</dt>
                    <dd className="text-right tabular-nums">{formatarPreco(m.imposto_devido)}</dd>
                  </dl>
                </li>
              ))}
            </ul>

            <div className="hidden overflow-x-auto rounded-xl border bg-card lg:block">
              <table className="w-full text-sm">
                <thead className="border-b text-left text-muted-foreground">
                  <tr>
                    {["Mês", "Vendas de ações", "Ações", "ETFs e BDRs", "FIIs", "Day trade", "Prejuízo usado", "Imposto", "IRRF usado", "DARF", "Situação"].map((c, i) => (
                      <th key={c} scope="col" className={cn("px-3 py-2 font-medium", i > 0 && i < 10 && "text-right")}>
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y [&_td]:whitespace-nowrap [&_td:last-child]:whitespace-normal">
                  {dados.meses.map((m) => (
                    <tr key={m.mes}>
                      <th scope="row" className="whitespace-nowrap px-3 py-2 text-left font-medium">
                        {nomeMes(m.mes)}
                      </th>
                      <td className="px-3 py-2 text-right tabular-nums">{formatarPreco(m.vendas_acoes)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        <Resultado v={m.resultado_acoes} />
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        <Resultado v={m.resultado_etf_bdr} />
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        <Resultado v={m.resultado_fii} />
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        <Resultado v={m.resultado_day_trade} />
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">{n(m.compensado) > 0 ? formatarPreco(m.compensado) : "—"}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{n(m.imposto_devido) > 0 ? formatarPreco(m.imposto_devido) : "—"}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{n(m.irrf_usado) > 0 ? formatarPreco(m.irrf_usado) : "—"}</td>
                      <td className="px-3 py-2 text-right font-semibold tabular-nums">{n(m.darf) > 0 ? formatarPreco(m.darf) : "—"}</td>
                      <td className="min-w-56 px-3 py-2 text-muted-foreground">{situacao(m)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section aria-labelledby="titulo-pagar" className="grid gap-4 md:grid-cols-2">
            <div className="grid content-start gap-2 rounded-xl border bg-card p-5 text-sm">
              <h2 id="titulo-pagar" className="text-lg font-semibold">
                Como pagar o DARF
              </h2>
              <p className="text-muted-foreground">
                Gere o DARF no Sicalc Web, no site da Receita Federal, com o código <span className="font-medium text-foreground">{dados.codigo_darf}</span>, o
                último dia do mês de apuração como período e o valor desta página. Pago depois do vencimento, ele tem multa e juros, que o Sicalc calcula.
              </p>
            </div>
            <div className="grid content-start gap-2 rounded-xl border bg-card p-5 text-sm">
              <h2 className="text-lg font-semibold">Na declaração anual</h2>
              <ul className="grid gap-1 text-muted-foreground">
                {dados.anos.map((a) => (
                  <li key={a.ano}>
                    <span className="font-medium text-foreground">{a.ano}:</span> ganhos isentos com ações de {formatarPreco(a.ganho_isento)} e DARFs de{" "}
                    {formatarPreco(a.darf)}.
                  </li>
                ))}
              </ul>
              <p className="text-xs text-muted-foreground">
                Os ganhos isentos vão em Rendimentos Isentos e Não Tributáveis; o mês a mês vai em Renda Variável.{" "}
                <Link href={`/carteira/declaracao?c=${carteira.id}`} className="text-azul underline-offset-2 hover:underline">
                  Ver tudo para a declaração
                </Link>
              </p>
            </div>
          </section>

          <p className="text-xs text-muted-foreground">{dados.aviso}</p>
        </>
      )}
    </div>
  );
}

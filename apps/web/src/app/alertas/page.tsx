import { BellOff, BellRing, Trash2 } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { auth } from "@/auth";
import { CanaisNotificacao } from "@/components/alertas/canais";
import { FormularioAlerta } from "@/components/alertas/formulario-alerta";
import { Button } from "@/components/ui/button";
import { alternarAlerta, excluirAlerta } from "@/lib/acoes-alertas";
import { chamarApi } from "@/lib/api";
import { formatarData } from "@/lib/formato";
import type { Alertas, Notificacoes } from "@/lib/tipos-api";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Alertas", robots: { index: false } };
export const dynamic = "force-dynamic";

type Props = { searchParams: Promise<{ ticker?: string }> };

export default async function PaginaAlertas({ searchParams }: Props) {
  if (!(await auth())?.user) redirect("/entrar?voltar=/alertas");
  const [resp, respCanais] = await Promise.all([
    chamarApi("/v1/alertas", { cache: "no-store" }),
    chamarApi("/v1/notificacoes", { cache: "no-store" }),
  ]);
  if (resp.status === 401) redirect("/entrar?voltar=/alertas");
  if (!resp.ok) throw new Error(`API ${resp.status} em /v1/alertas`);
  const dados = (await resp.json()) as Alertas;
  const canais = respCanais.ok ? ((await respCanais.json()) as Notificacoes) : null;
  const semCanal = canais !== null && canais.push.aparelhos.length === 0 && !(canais.whatsapp.confirmado && canais.whatsapp.ativo);
  const { ticker = "" } = await searchParams;
  const cheio = dados.ligados >= dados.limite;

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-8">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Alertas</h1>
        <p className="mt-1 max-w-2xl text-muted-foreground">
          Avaliados no fim de cada pregão. Quando um alerta dispara, você recebe no mesmo dia, pela notificação do aparelho ou pelo WhatsApp, tudo o que
          disparou.
        </p>
      </div>

      {canais && (
        <section aria-labelledby="titulo-canais" className="grid gap-3">
          <div>
            <h2 id="titulo-canais" className="text-xl font-semibold">
              Onde avisar
            </h2>
            {semCanal && (
              <p className="mt-1 text-sm text-muted-foreground">Ligue pelo menos um dos dois para receber os alertas. Até lá, eles ficam só nesta página.</p>
            )}
          </div>
          <CanaisNotificacao estado={canais} />
        </section>
      )}

      <section aria-labelledby="titulo-novo" className="grid gap-3 rounded-xl border bg-card p-4">
        <h2 id="titulo-novo" className="font-semibold">
          Novo alerta
        </h2>
        <FormularioAlerta ticker={/^[A-Za-z0-9]{4,6}$/.test(ticker) ? ticker.toUpperCase() : ""} sinais={dados.sinais} desabilitado={cheio} />
        <p className="text-xs text-muted-foreground">
          {cheio
            ? `Você chegou ao limite de ${dados.limite} alertas ligados. Desligue ou exclua um para criar outro.`
            : `${dados.ligados} de ${dados.limite} alertas ligados. Os de preço disparam no pregão em que o fechamento cruza o valor.`}
        </p>
      </section>

      <section aria-labelledby="titulo-lista" className="grid gap-3">
        <h2 id="titulo-lista" className="text-xl font-semibold">
          Seus alertas
        </h2>
        {dados.itens.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nenhum alerta ainda. Você também pode criar a partir da <Link href="/watchlist" className="underline">watchlist</Link>.
          </p>
        ) : (
          <ul className="divide-y rounded-xl border bg-card">
            {dados.itens.map((a) => (
              <li key={a.id} className={cn("flex flex-wrap items-center gap-x-4 gap-y-2 p-3", !a.ativo && "text-muted-foreground")}>
                <Link href={`/ativo/${a.ticker}`} className="w-16 font-semibold hover:underline">
                  {a.ticker}
                </Link>
                <div className="min-w-0 flex-1">
                  <p className="text-sm">{a.descricao}</p>
                  <p className="text-xs text-muted-foreground">
                    {a.ativo ? "Ligado" : "Desligado"}
                    {a.ultimo_disparo && ` · último disparo em ${formatarData(a.ultimo_disparo)}`}
                  </p>
                </div>
                <div className="flex gap-1">
                  <form action={alternarAlerta}>
                    <input type="hidden" name="alerta" value={a.id} />
                    <input type="hidden" name="ativo" value={a.ativo ? "0" : "1"} />
                    <Button type="submit" variant="ghost" size="sm" disabled={!a.ativo && cheio}>
                      {a.ativo ? <BellOff aria-hidden /> : <BellRing aria-hidden />}
                      {a.ativo ? "Desligar" : "Ligar"}
                      <span className="sr-only"> o alerta de {a.ticker}</span>
                    </Button>
                  </form>
                  <form action={excluirAlerta}>
                    <input type="hidden" name="alerta" value={a.id} />
                    <Button type="submit" variant="ghost" size="icon" title="Excluir alerta">
                      <Trash2 aria-hidden />
                      <span className="sr-only">Excluir o alerta de {a.ticker}: {a.descricao}</span>
                    </Button>
                  </form>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {dados.disparos.length > 0 && (
        <section aria-labelledby="titulo-disparos" className="grid gap-3">
          <h2 id="titulo-disparos" className="text-xl font-semibold">
            Últimos disparos
          </h2>
          <ul className="grid gap-2 text-sm">
            {dados.disparos.map((d) => (
              <li key={`${d.alerta_id}-${d.data}`} className="flex flex-wrap justify-between gap-x-4">
                <span>{d.texto}</span>
                <span className="text-xs text-muted-foreground">{descreverEntrega(d.canais)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

const NOME_CANAL: Record<string, string> = { push: "notificação", whatsapp: "WhatsApp", email: "e-mail" };

function descreverEntrega(canais: string[]): string {
  if (canais.length === 0) return "ainda não entregue";
  return `entregue por ${canais.map((c) => NOME_CANAL[c] ?? c).join(" e ")}`;
}

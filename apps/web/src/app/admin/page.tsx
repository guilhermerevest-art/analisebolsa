import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";

import { auth } from "@/auth";
import { chamarApi } from "@/lib/api";
import { formatarNumero } from "@/lib/formato";
import type { Execucoes } from "@/lib/tipos-api";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Admin", robots: { index: false } };
export const dynamic = "force-dynamic";

const CORES = {
  ok: "bg-positivo/15 text-positivo",
  parcial: "bg-amber-500/15 text-amber-600",
  erro: "bg-destructive/15 text-destructive",
  rodando: "bg-muted text-muted-foreground",
} as const;

function dataHora(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("pt-BR", { timeZone: "America/Sao_Paulo", dateStyle: "short", timeStyle: "short" });
}

function duracao(inicio: string, fim: string | null): string {
  if (!fim) return "—";
  const s = Math.round((new Date(fim).getTime() - new Date(inicio).getTime()) / 1000);
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${s % 60} s`;
}

export default async function Admin() {
  const sessao = await auth();
  if (!sessao?.user) redirect("/entrar");
  if (sessao.user.role !== "admin") notFound();

  const resp = await chamarApi("/v1/admin/execucoes?limite=50", { cache: "no-store" });
  const dados = resp.ok ? ((await resp.json()) as Execucoes) : null;

  return (
    <div className="grid gap-6">
      <h1 className="text-2xl font-bold tracking-tight">Execuções do job</h1>
      {!dados ? (
        <p className="text-sm text-destructive">Não foi possível consultar a API (HTTP {resp.status}).</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-muted-foreground">
              <tr>
                <th className="py-2 pr-4 font-normal">#</th>
                <th className="py-2 pr-4 font-normal">Tipo</th>
                <th className="py-2 pr-4 font-normal">Status</th>
                <th className="py-2 pr-4 font-normal">Início</th>
                <th className="py-2 pr-4 font-normal">Duração</th>
                <th className="py-2 pr-4 text-right font-normal">Ativos OK</th>
                <th className="py-2 pr-4 text-right font-normal">Com erro</th>
                <th className="py-2 font-normal">Detalhes</th>
              </tr>
            </thead>
            <tbody>
              {dados.itens.map((e) => {
                const erros = Object.keys((e.detalhes.erros as Record<string, string>) ?? {});
                const alertas = Object.keys((e.detalhes.alertas as Record<string, unknown>) ?? {});
                return (
                  <tr key={e.execucao_id} className="border-t align-top">
                    <td className="py-2 pr-4 tabular-nums">{e.execucao_id}</td>
                    <td className="py-2 pr-4">{e.tipo}</td>
                    <td className="py-2 pr-4">
                      <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", CORES[e.status])}>{e.status}</span>
                    </td>
                    <td className="py-2 pr-4 whitespace-nowrap">{dataHora(e.iniciado_em)}</td>
                    <td className="py-2 pr-4 whitespace-nowrap">{duracao(e.iniciado_em, e.finalizado_em)}</td>
                    <td className="py-2 pr-4 text-right tabular-nums">{formatarNumero(e.ativos_ok, 0)}</td>
                    <td className="py-2 pr-4 text-right tabular-nums">{formatarNumero(e.ativos_erro, 0)}</td>
                    <td className="py-2 text-xs text-muted-foreground">
                      {erros.length > 0 && <p>Erros: {erros.slice(0, 8).join(", ")}{erros.length > 8 && ` e mais ${erros.length - 8}`}</p>}
                      {alertas.length > 0 && <p>Alertas: {alertas.join(", ")}</p>}
                      {typeof e.detalhes.erro === "string" && <p>{e.detalhes.erro}</p>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

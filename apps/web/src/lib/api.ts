import "server-only";

import { auth } from "@/auth";
import { cabecalhosApi, env } from "@/lib/env";
import { assinarTokenInterno } from "@/lib/jwt-interno";

/** Chamada à API interna, com o JWT interno quando há sessão. */
export async function chamarApi(caminho: string, init: RequestInit & { next?: NextFetchRequestConfig } = {}) {
  const headers = new Headers(init.headers);
  for (const [nome, valor] of Object.entries(cabecalhosApi())) headers.set(nome, valor);
  const sessao = await auth();
  if (sessao?.user?.id) {
    const token = await assinarTokenInterno(
      { sub: sessao.user.id, plano: sessao.user.plano, role: sessao.user.role },
      env("INTERNAL_JWT_SECRET"),
    );
    headers.set("Authorization", `Bearer ${token}`);
  }
  return fetch(`${env("API_INTERNAL_URL").replace(/\/$/, "")}${caminho}`, { ...init, headers });
}

/** Escrita na API interna (sem cache), devolvendo o detalhe do erro em RFC 7807. */
export async function enviarApi(
  caminho: string,
  metodo: string,
  corpo?: unknown,
): Promise<{ ok: boolean; status: number; detalhe?: string; dados?: unknown }> {
  const resp = await chamarApi(caminho, {
    method: metodo,
    cache: "no-store",
    headers: corpo === undefined ? undefined : { "Content-Type": "application/json" },
    body: corpo === undefined ? undefined : JSON.stringify(corpo),
  });
  const dados = resp.status === 204 ? undefined : await resp.json().catch(() => undefined);
  const detalhe = (dados as { detail?: unknown } | undefined)?.detail;
  return { ok: resp.ok, status: resp.status, dados, detalhe: typeof detalhe === "string" ? detalhe : undefined };
}

import "server-only";

import { auth } from "@/auth";
import { env } from "@/lib/env";
import { assinarTokenInterno } from "@/lib/jwt-interno";

/** Chamada à API interna, com o JWT interno quando há sessão. */
export async function chamarApi(caminho: string, init: RequestInit & { next?: NextFetchRequestConfig } = {}) {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
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

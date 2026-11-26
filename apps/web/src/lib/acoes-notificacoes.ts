"use server";

import { revalidatePath } from "next/cache";
import { z } from "zod";

import { enviarApi } from "@/lib/api";

export type EstadoCanal = { erro?: string; ok?: number; mensagem?: string };

const inscricao = z.object({
  endpoint: z.string().url().startsWith("https://").max(1000),
  keys: z.object({ p256dh: z.string().min(20).max(200), auth: z.string().min(8).max(100) }),
});

/** Registra a inscrição de push deste aparelho (o navegador já pediu a permissão). */
export async function registrarPush(sub: unknown, aparelho: string): Promise<EstadoCanal> {
  const parsed = inscricao.safeParse(sub);
  if (!parsed.success) return { erro: "O navegador devolveu uma inscrição inválida" };
  const r = await enviarApi("/v1/notificacoes/push", "POST", { ...parsed.data, aparelho: aparelho.slice(0, 80) || null });
  if (!r.ok) return { erro: r.detalhe ?? "Não foi possível ligar as notificações" };
  revalidatePath("/alertas");
  return { ok: Date.now() };
}

export async function cancelarPush(endpoint: string): Promise<void> {
  if (endpoint.startsWith("https://")) await enviarApi("/v1/notificacoes/push/cancelar", "POST", { endpoint });
  revalidatePath("/alertas");
}

export async function testarPush(): Promise<EstadoCanal> {
  const r = await enviarApi("/v1/notificacoes/push/teste", "POST");
  if (!r.ok) return { erro: r.detalhe ?? "Não foi possível enviar o teste" };
  const n = (r.dados as { enviados?: number } | undefined)?.enviados ?? 0;
  revalidatePath("/alertas");
  return n > 0
    ? { ok: Date.now(), mensagem: n === 1 ? "Teste enviado para 1 aparelho." : `Teste enviado para ${n} aparelhos.` }
    : { erro: "Nenhum aparelho recebeu. Ligue as notificações de novo neste aparelho." };
}

export async function removerAparelho(form: FormData): Promise<void> {
  const id = Number(form.get("aparelho"));
  if (Number.isInteger(id) && id > 0) await enviarApi(`/v1/notificacoes/push/${id}`, "DELETE");
  revalidatePath("/alertas");
}

export async function cadastrarWhatsapp(_: EstadoCanal, form: FormData): Promise<EstadoCanal> {
  const numero = String(form.get("numero") ?? "").trim();
  if (numero.replace(/\D/g, "").length < 10) return { erro: "Informe o DDD e o número, ex.: (11) 98765-4321" };
  const r = await enviarApi("/v1/notificacoes/whatsapp", "PUT", { numero });
  if (!r.ok) return { erro: r.detalhe ? capitalizar(r.detalhe) : "Não foi possível enviar o código" };
  revalidatePath("/alertas");
  return { ok: Date.now() };
}

export async function confirmarWhatsapp(_: EstadoCanal, form: FormData): Promise<EstadoCanal> {
  const codigo = String(form.get("codigo") ?? "").replace(/\D/g, "");
  if (codigo.length !== 6) return { erro: "O código tem 6 dígitos" };
  const r = await enviarApi("/v1/notificacoes/whatsapp/confirmar", "POST", { codigo });
  if (!r.ok) return { erro: r.detalhe ? capitalizar(r.detalhe) : "Não foi possível confirmar" };
  revalidatePath("/alertas");
  return { ok: Date.now() };
}

export async function alternarWhatsapp(form: FormData): Promise<void> {
  await enviarApi("/v1/notificacoes/whatsapp", "PATCH", { ativo: form.get("ativo") === "1" });
  revalidatePath("/alertas");
}

export async function removerWhatsapp(): Promise<void> {
  await enviarApi("/v1/notificacoes/whatsapp", "DELETE");
  revalidatePath("/alertas");
}

function capitalizar(t: string) {
  return t.charAt(0).toUpperCase() + t.slice(1);
}

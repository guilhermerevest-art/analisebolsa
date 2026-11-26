"use server";

import { revalidatePath } from "next/cache";

import { chamarApi, enviarApi } from "@/lib/api";
import type { EstadoInstancia } from "@/lib/tipos-api";

export type EstadoForm = { erro?: string; ok?: number; mensagem?: string };

const capitalizar = (t: string) => t.charAt(0).toUpperCase() + t.slice(1);

export async function salvarWhatsapp(_: EstadoForm, form: FormData): Promise<EstadoForm> {
  const corpo = {
    url: String(form.get("url") ?? "").trim(),
    instancia: String(form.get("instancia") ?? "").trim(),
    chave: String(form.get("chave") ?? "").trim() || null,
    ativo: form.get("ativo") === "on",
  };
  if (!corpo.url || !corpo.instancia) return { erro: "Informe a URL e o nome da instância" };
  const r = await enviarApi("/v1/admin/whatsapp", "PUT", corpo);
  if (!r.ok) return { erro: r.detalhe ? capitalizar(r.detalhe) : `Não foi possível salvar (HTTP ${r.status})` };
  revalidatePath("/admin");
  return { ok: Date.now(), mensagem: "Instância salva." };
}

export async function removerWhatsappAdmin(): Promise<void> {
  await enviarApi("/v1/admin/whatsapp", "DELETE");
  revalidatePath("/admin");
}

export async function lerEstadoWhatsapp(): Promise<EstadoInstancia | null> {
  const r = await chamarApi("/v1/admin/whatsapp/estado", { cache: "no-store" });
  return r.ok ? ((await r.json()) as EstadoInstancia) : null;
}

export async function testarWhatsappAdmin(_: EstadoForm, form: FormData): Promise<EstadoForm> {
  const numero = String(form.get("numero") ?? "").trim();
  if (numero.replace(/\D/g, "").length < 10) return { erro: "Informe o número com DDD" };
  const r = await enviarApi("/v1/admin/whatsapp/teste", "POST", { numero });
  if (!r.ok) return { erro: r.detalhe ? capitalizar(r.detalhe) : `Falhou (HTTP ${r.status})` };
  return { ok: Date.now(), mensagem: "Mensagem de teste enviada. Confira no WhatsApp." };
}

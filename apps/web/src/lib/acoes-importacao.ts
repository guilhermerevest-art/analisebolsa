"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { enviarApi } from "@/lib/api";
import type { PreviaImportacao } from "@/lib/tipos-api";

export type EstadoImportacao = { previa?: PreviaImportacao; erro?: string };

const MAXIMO = 2 * 1024 * 1024;

async function lerArquivo(form: FormData): Promise<{ carteira: number; arquivo: string } | { erro: string }> {
  const carteira = Number(form.get("carteira"));
  const arquivo = form.get("arquivo");
  if (!Number.isInteger(carteira) || carteira <= 0) return { erro: "Carteira inválida" };
  if (!(arquivo instanceof File) || arquivo.size === 0) return { erro: "Escolha o arquivo .xlsx baixado da B3" };
  if (arquivo.size > MAXIMO) return { erro: "O arquivo passa de 2 MB. Baixe um período menor." };
  if (!/\.xlsx$/i.test(arquivo.name)) return { erro: "O arquivo precisa ser .xlsx (Excel), como a B3 entrega" };
  return { carteira, arquivo: Buffer.from(await arquivo.arrayBuffer()).toString("base64") };
}

const capitalizar = (t: string) => t.charAt(0).toUpperCase() + t.slice(1);

export async function previaImportacao(_: EstadoImportacao, form: FormData): Promise<EstadoImportacao> {
  const lido = await lerArquivo(form);
  if ("erro" in lido) return { erro: lido.erro };
  const r = await enviarApi(`/v1/carteiras/${lido.carteira}/importacao/previa`, "POST", { arquivo: lido.arquivo });
  if (!r.ok) return { erro: r.detalhe ? capitalizar(r.detalhe) : "Não foi possível ler a planilha agora" };
  return { previa: r.dados as PreviaImportacao };
}

export async function importarB3(estado: EstadoImportacao, form: FormData): Promise<EstadoImportacao> {
  const lido = await lerArquivo(form);
  if ("erro" in lido) return { ...estado, erro: lido.erro };
  const r = await enviarApi(`/v1/carteiras/${lido.carteira}/importacao`, "POST", { arquivo: lido.arquivo });
  if (!r.ok) return { ...estado, erro: r.detalhe ? capitalizar(r.detalhe) : "Não foi possível importar agora" };
  const n = (r.dados as { importadas: number }).importadas;
  revalidatePath("/carteira");
  redirect(`/carteira?c=${lido.carteira}&importadas=${n}`);
}

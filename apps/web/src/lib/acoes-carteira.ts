"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { enviarApi as enviar } from "@/lib/api";
import { decimalBr, esquemaOperacao, errosPorCampo, type ErrosCampos } from "@/lib/validacao";

export type EstadoOperacao = { erros?: ErrosCampos; ok?: number };

const id = (v: FormDataEntryValue | null) => {
  const n = Number(v);
  return Number.isInteger(n) && n > 0 ? n : null;
};

export async function criarCarteira(form: FormData): Promise<void> {
  const nome = String(form.get("nome") ?? "").trim() || "Minha carteira";
  const r = await enviar("/v1/carteiras", "POST", { nome: nome.slice(0, 60) });
  revalidatePath("/carteira");
  const nova = r.ok ? (r.dados as { id: number }).id : null;
  redirect(nova ? `/carteira?c=${nova}` : "/carteira");
}

export async function renomearCarteira(form: FormData): Promise<void> {
  const c = id(form.get("carteira"));
  const nome = String(form.get("nome") ?? "").trim().slice(0, 60);
  if (c && nome) await enviar(`/v1/carteiras/${c}`, "PATCH", { nome });
  revalidatePath("/carteira");
}

export async function excluirCarteira(form: FormData): Promise<void> {
  const c = id(form.get("carteira"));
  if (c) await enviar(`/v1/carteiras/${c}`, "DELETE");
  revalidatePath("/carteira");
  redirect("/carteira");
}

export async function lancarOperacao(_: EstadoOperacao, form: FormData): Promise<EstadoOperacao> {
  const c = id(form.get("carteira"));
  if (!c) return { erros: { form: "Carteira inválida" } };
  const parsed = esquemaOperacao.safeParse(Object.fromEntries(["ticker", "tipo", "data", "quantidade", "preco", "custos"].map((k) => [k, String(form.get(k) ?? "")])));
  if (!parsed.success) return { erros: errosPorCampo(parsed.error) };
  const r = await enviar(`/v1/carteiras/${c}/operacoes`, "POST", parsed.data);
  if (!r.ok) return { erros: { form: r.detalhe ?? "Não foi possível lançar a operação" } };
  revalidatePath("/carteira");
  return { ok: Date.now() };
}

export async function editarOperacao(_: EstadoOperacao, form: FormData): Promise<EstadoOperacao> {
  const c = id(form.get("carteira"));
  const op = id(form.get("operacao"));
  if (!c || !op) return { erros: { form: "Operação inválida" } };
  const parsed = esquemaOperacao.safeParse(Object.fromEntries(["ticker", "tipo", "data", "quantidade", "preco", "custos"].map((k) => [k, String(form.get(k) ?? "")])));
  if (!parsed.success) return { erros: errosPorCampo(parsed.error) };
  const r = await enviar(`/v1/carteiras/${c}/operacoes/${op}`, "PUT", parsed.data);
  if (r.status === 404) return { erros: { form: "Operação não encontrada" } };
  if (!r.ok) return { erros: { form: r.detalhe ?? "Não foi possível salvar a operação" } };
  revalidatePath("/carteira");
  redirect(`/carteira?c=${c}&editada=1`);
}

export async function removerOperacao(form: FormData): Promise<void> {
  const c = id(form.get("carteira"));
  const op = id(form.get("operacao"));
  if (c && op) await enviar(`/v1/carteiras/${c}/operacoes/${op}`, "DELETE");
  revalidatePath("/carteira");
}

export type EstadoInvestimento = { erros?: ErrosCampos; ok?: number; valores?: Record<string, string> };

/** Monta o corpo da API a partir do formulário; os campos que não valem para o tipo ficam de fora. */
function corpoInvestimento(form: FormData): { corpo?: Record<string, unknown>; erros?: ErrosCampos } {
  const texto = (k: string) => String(form.get(k) ?? "").trim();
  const tipo = texto("tipo");
  const fundo = tipo === "fundo";
  const erros: ErrosCampos = {};
  const numero = (k: string, rotulo: string, obrigatorio: boolean) => {
    const v = texto(k);
    if (!v) {
      if (obrigatorio) erros[k] = `Informe ${rotulo}`;
      return null;
    }
    const d = decimalBr(v);
    if (d === null) erros[k] = `${rotulo.charAt(0).toUpperCase()}${rotulo.slice(1)} inválido`;
    return d;
  };
  const nome = texto("nome");
  if (!nome) erros.nome = "Dê um nome, como o emissor e o vencimento";
  if (!texto("data_aplicacao")) erros.data_aplicacao = "Informe a data da aplicação";
  const corpo: Record<string, unknown> = {
    tipo,
    nome: nome.slice(0, 80),
    data_aplicacao: texto("data_aplicacao"),
    valor_aplicado: numero("valor_aplicado", "o valor aplicado", true),
  };
  if (fundo) {
    corpo.cnpj = texto("cnpj");
    if (!corpo.cnpj) erros.cnpj = "Informe o CNPJ do fundo";
    corpo.cotas = numero("cotas", "o número de cotas", false);
  } else {
    corpo.indexador = texto("indexador");
    corpo.taxa = Number(numero("taxa", "a taxa", true));
    corpo.vencimento = texto("vencimento") || null;
    corpo.isento_ir = form.get("isento_ir") === "on";
  }
  const resgateData = texto("resgate_data");
  const resgateValor = numero("resgate_valor", "o valor do resgate", Boolean(resgateData));
  if (resgateValor && !resgateData) erros.resgate_data = "Informe a data do resgate";
  if (resgateData) Object.assign(corpo, { resgate_data: resgateData, resgate_valor: resgateValor });
  return Object.keys(erros).length ? { erros } : { corpo };
}

export async function salvarInvestimento(_: EstadoInvestimento, form: FormData): Promise<EstadoInvestimento> {
  const c = id(form.get("carteira"));
  if (!c) return { erros: { form: "Carteira inválida" } };
  const inv = id(form.get("investimento"));
  // O React limpa o formulário depois da ação; os valores voltam para não perder o que foi digitado.
  const valores = Object.fromEntries([...form.entries()].filter(([, v]) => typeof v === "string")) as Record<string, string>;
  const { corpo, erros } = corpoInvestimento(form);
  if (!corpo) return { erros, valores };
  const r = await enviar(`/v1/carteiras/${c}/investimentos${inv ? `/${inv}` : ""}`, inv ? "PUT" : "POST", corpo);
  if (r.status === 404) return { erros: { form: "Investimento não encontrado" }, valores };
  if (!r.ok) return { erros: { form: r.detalhe ?? "Confira os campos: algum valor está fora do permitido" }, valores };
  revalidatePath("/carteira");
  if (inv) redirect(`/carteira?c=${c}#renda-fixa`);
  return { ok: Date.now() };
}

export async function removerInvestimento(form: FormData): Promise<void> {
  const c = id(form.get("carteira"));
  const inv = id(form.get("investimento"));
  if (c && inv) await enviar(`/v1/carteiras/${c}/investimentos/${inv}`, "DELETE");
  revalidatePath("/carteira");
}

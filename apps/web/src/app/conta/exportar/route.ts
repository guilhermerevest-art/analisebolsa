import { chamarApi } from "@/lib/api";

export const dynamic = "force-dynamic";

/** Baixa todos os dados do usuário em JSON (LGPD). */
export async function GET() {
  const resp = await chamarApi("/v1/conta/exportar", { cache: "no-store" });
  if (resp.status === 401) return new Response("Entre na sua conta para exportar os dados.", { status: 401 });
  if (!resp.ok) return new Response("Não foi possível exportar agora.", { status: 502 });
  const hoje = new Date().toISOString().slice(0, 10);
  return new Response(JSON.stringify(await resp.json(), null, 2), {
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Content-Disposition": `attachment; filename="analisebolsa-meus-dados-${hoje}.json"`,
      "Cache-Control": "private, no-store",
    },
  });
}

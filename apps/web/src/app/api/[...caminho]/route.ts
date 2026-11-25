import { type NextRequest, NextResponse } from "next/server";

import { chamarApi } from "@/lib/api";
import { cacheControl, caminhoApi } from "@/lib/bff";

/** BFF: repassa GET /api/<rota> para a API interna em /v1/<rota>. */
export async function GET(req: NextRequest, { params }: { params: Promise<{ caminho: string[] }> }) {
  const { caminho } = await params;
  const destino = caminhoApi(caminho);
  if (!destino) {
    return NextResponse.json(
      { type: "about:blank", title: "Not Found", status: 404 },
      { status: 404, headers: { "Content-Type": "application/problem+json" } },
    );
  }
  let resp: Response;
  try {
    resp = await chamarApi(`${destino}${req.nextUrl.search}`, { cache: "no-store" });
  } catch {
    return NextResponse.json(
      { type: "about:blank", title: "Bad Gateway", status: 502, detail: "API indisponível" },
      { status: 502, headers: { "Content-Type": "application/problem+json" } },
    );
  }
  return new NextResponse(resp.body, {
    status: resp.status,
    headers: {
      "Content-Type": resp.headers.get("Content-Type") ?? "application/json",
      "Cache-Control": resp.ok ? cacheControl(caminho) : "no-store",
    },
  });
}

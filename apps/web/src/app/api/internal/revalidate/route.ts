import { revalidateTag } from "next/cache";
import { type NextRequest, NextResponse } from "next/server";
import { z } from "zod";

import { tagValida } from "@/lib/bff";
import { env } from "@/lib/env";
import { verificarTokenInterno } from "@/lib/jwt-interno";

const corpo = z.object({ tags: z.array(z.string()).max(5000) });

/** Chamado pelo worker no fim do EOD para renovar o cache das páginas. */
export async function POST(req: NextRequest) {
  const token = req.headers.get("authorization")?.replace(/^Bearer\s+/i, "");
  try {
    if (!token) throw new Error("sem token");
    await verificarTokenInterno(token, env("INTERNAL_JWT_SECRET"));
  } catch {
    return NextResponse.json({ erro: "não autorizado" }, { status: 401 });
  }
  const parsed = corpo.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return NextResponse.json({ erro: "corpo inválido" }, { status: 400 });
  const tags = parsed.data.tags.filter(tagValida);
  for (const tag of tags) revalidateTag(tag);
  return NextResponse.json({ revalidadas: tags.length });
}

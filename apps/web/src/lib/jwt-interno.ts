/**
 * JWT interno HS256 entre web, api e worker (spec, seção 5): `exp` de no máximo 60 s.
 */
import { jwtVerify, SignJWT } from "jose";

export const VALIDADE_S = 60;
const FOLGA_S = 5;

export type ClaimsInternas = { sub: string; plano: string; role: "user" | "admin" };

function chave(segredo: string): Uint8Array {
  if (new TextEncoder().encode(segredo).length < 32) {
    throw new Error("INTERNAL_JWT_SECRET precisa ter pelo menos 32 bytes");
  }
  return new TextEncoder().encode(segredo);
}

export async function assinarTokenInterno(
  claims: ClaimsInternas,
  segredo: string,
  agora = Math.floor(Date.now() / 1000),
): Promise<string> {
  return new SignJWT({ plano: claims.plano, role: claims.role })
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(claims.sub)
    .setIssuedAt(agora)
    .setExpirationTime(agora + VALIDADE_S)
    .sign(chave(segredo));
}

/** Valida assinatura, expiração e a validade máxima. Lança erro se o token não servir. */
export async function verificarTokenInterno(
  token: string,
  segredo: string,
  agora = Math.floor(Date.now() / 1000),
): Promise<ClaimsInternas> {
  const { payload } = await jwtVerify(token, chave(segredo), {
    algorithms: ["HS256"],
    currentDate: new Date(agora * 1000),
    clockTolerance: FOLGA_S,
    requiredClaims: ["exp", "sub"],
  });
  if ((payload.exp ?? 0) - agora > VALIDADE_S + FOLGA_S) {
    throw new Error("token com validade acima de 60 s");
  }
  return {
    sub: String(payload.sub),
    plano: String(payload.plano ?? "free"),
    role: payload.role === "admin" ? "admin" : "user",
  };
}

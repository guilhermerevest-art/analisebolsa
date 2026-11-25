import { SignJWT } from "jose";
import { describe, expect, it } from "vitest";

import { assinarTokenInterno, verificarTokenInterno } from "./jwt-interno";

const SEGREDO = "segredo-de-teste-com-mais-de-32-bytes!!";
const AGORA = 1_800_000_000;
const claims = { sub: "u1", plano: "free", role: "admin" as const };

describe("JWT interno", () => {
  it("assina e verifica com validade de 60 s", async () => {
    const token = await assinarTokenInterno(claims, SEGREDO, AGORA);
    await expect(verificarTokenInterno(token, SEGREDO, AGORA + 30)).resolves.toEqual(claims);
  });

  it("rejeita token expirado", async () => {
    const token = await assinarTokenInterno(claims, SEGREDO, AGORA);
    await expect(verificarTokenInterno(token, SEGREDO, AGORA + 120)).rejects.toThrow();
  });

  it("rejeita assinatura errada", async () => {
    const token = await assinarTokenInterno(claims, "outro-segredo-com-mais-de-32-bytes!!!", AGORA);
    await expect(verificarTokenInterno(token, SEGREDO, AGORA)).rejects.toThrow();
  });

  it("rejeita validade acima de 60 s", async () => {
    const token = await new SignJWT({ role: "admin" })
      .setProtectedHeader({ alg: "HS256" })
      .setSubject("u1")
      .setExpirationTime(AGORA + 3600)
      .sign(new TextEncoder().encode(SEGREDO));
    await expect(verificarTokenInterno(token, SEGREDO, AGORA)).rejects.toThrow("60 s");
  });

  it("exige segredo de pelo menos 32 bytes", async () => {
    await expect(assinarTokenInterno(claims, "curto")).rejects.toThrow("32 bytes");
  });

  it("role desconhecido vira user", async () => {
    const token = await new SignJWT({ role: "root" })
      .setProtectedHeader({ alg: "HS256" })
      .setSubject("u1")
      .setExpirationTime(AGORA + 60)
      .sign(new TextEncoder().encode(SEGREDO));
    expect((await verificarTokenInterno(token, SEGREDO, AGORA)).role).toBe("user");
  });
});

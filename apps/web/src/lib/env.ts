/** Variáveis de ambiente do servidor (spec, seção 8). Lidas sob demanda para o build não exigir segredos. */
export function env(nome: string): string {
  const valor = process.env[nome];
  if (!valor) throw new Error(`variável de ambiente ${nome} não definida`);
  return valor;
}

export function googleHabilitado(): boolean {
  return Boolean(process.env.AUTH_GOOGLE_ID && process.env.AUTH_GOOGLE_SECRET);
}

/** Lista de ADMIN_EMAILS normalizada (minúsculas, sem espaços). */
export function emailsAdmin(valor = process.env.ADMIN_EMAILS ?? ""): Set<string> {
  return new Set(
    valor
      .split(",")
      .map((e) => e.trim().toLowerCase())
      .filter(Boolean),
  );
}

export function roleParaEmail(email: string | null | undefined, admins = emailsAdmin()): "admin" | "user" {
  return email && admins.has(email.trim().toLowerCase()) ? "admin" : "user";
}

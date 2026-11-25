import { DrizzleAdapter } from "@auth/drizzle-adapter";
import { verify } from "@node-rs/argon2";
import { eq } from "drizzle-orm";
import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import Google from "next-auth/providers/google";

import { db, schema } from "@/lib/db";
import { googleHabilitado, roleParaEmail } from "@/lib/env";
import { esquemaEntrar } from "@/lib/validacao";

/**
 * Auth.js v5. A sessão é um JWT criptografado em cookie httpOnly, porque o
 * provider Credentials não suporta sessão no banco (spec, seção 3).
 */
export const { handlers, auth, signIn, signOut } = NextAuth(() => ({
  adapter: DrizzleAdapter(db(), {
    usersTable: schema.users,
    accountsTable: schema.accounts,
    sessionsTable: schema.sessions,
    verificationTokensTable: schema.verificationTokens,
  }),
  session: { strategy: "jwt", maxAge: 30 * 24 * 60 * 60 },
  pages: { signIn: "/entrar" },
  trustHost: true,
  providers: [
    Credentials({
      credentials: { email: {}, senha: {} },
      async authorize(dados) {
        const parsed = esquemaEntrar.safeParse(dados);
        if (!parsed.success) return null;
        const [usuario] = await db()
          .select()
          .from(schema.users)
          .where(eq(schema.users.email, parsed.data.email))
          .limit(1);
        if (!usuario?.passwordHash) return null;
        if (!(await verify(usuario.passwordHash, parsed.data.senha))) return null;
        return { id: usuario.id, name: usuario.name, email: usuario.email, image: usuario.image };
      },
    }),
    ...(googleHabilitado() ? [Google] : []),
  ],
  events: {
    // Usuários criados pelo Google passam pelo adapter; aqui recebem o role certo.
    async createUser({ user }) {
      if (user.id && roleParaEmail(user.email) === "admin") {
        await db().update(schema.users).set({ role: "admin" }).where(eq(schema.users.id, user.id));
      }
    },
  },
  callbacks: {
    async jwt({ token, user, trigger }) {
      if (user?.id || trigger === "update") {
        const id = user?.id ?? token.sub;
        if (id) {
          const [linha] = await db()
            .select({ role: schema.users.role, plano: schema.users.plano })
            .from(schema.users)
            .where(eq(schema.users.id, id))
            .limit(1);
          token.sub = id;
          token.role = linha?.role ?? "user";
          token.plano = linha?.plano ?? "free";
        }
      }
      return token;
    },
    session({ session, token }) {
      if (token.sub) session.user.id = token.sub;
      session.user.role = token.role === "admin" ? "admin" : "user";
      session.user.plano = typeof token.plano === "string" ? token.plano : "free";
      return session;
    },
  },
}));

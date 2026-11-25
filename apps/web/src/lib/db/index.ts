import { drizzle, type PostgresJsDatabase } from "drizzle-orm/postgres-js";
import postgres from "postgres";

import { env } from "@/lib/env";
import * as schema from "./schema";

let instancia: PostgresJsDatabase<typeof schema> | undefined;

/** Conexão criada na primeira chamada, para o `next build` não precisar do banco. */
export function db(): PostgresJsDatabase<typeof schema> {
  instancia ??= drizzle(postgres(env("DATABASE_URL"), { max: 10 }), { schema });
  return instancia;
}

export { schema };

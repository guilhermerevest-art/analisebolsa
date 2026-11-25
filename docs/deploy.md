# Deploy em produção (Vercel)

Arquitetura:

| Peça | Onde roda | Como sobe |
|---|---|---|
| web (`apps/web`) | Projeto Vercel `analisebolsa`, região `gru1` | Push na `main` |
| api (`apps/api`) | Projeto Vercel `analisebolsa-api`, função Python (FastAPI), região `gru1` | Push na `main` |
| Postgres | Gerenciado (Supabase em `sa-east-1`) | Migrations pelo workflow `Migrations` |
| worker | GitHub Actions, workflow `Worker` | Cron `0 22 * * 1-5` (19h de Brasília) e sob demanda |

## 1. Banco

1. Crie o banco e anote duas strings de conexão do **pooler**:
   - modo transação (porta 6543) para a api na Vercel;
   - modo sessão (porta 5432) para migrations e worker no GitHub Actions, que só tem IPv4.
2. As duas terminam em `?sslmode=require`.

## 2. Segredos

Gere três segredos diferentes (por exemplo, `openssl rand -base64 48`):
`INTERNAL_JWT_SECRET`, `INTERNAL_API_KEY` e `AUTH_SECRET`.

## 3. Projeto da api na Vercel

- Root Directory: `apps/api`. O preset FastAPI é detectado pelo `[tool.vercel]` do `pyproject.toml`.
- Variáveis (Production):
  - `DATABASE_URL`: pooler em modo transação. Na Vercel, a api usa `NullPool` e desliga
    prepared statements sozinha (variável `VERCEL`).
  - `INTERNAL_JWT_SECRET`, `INTERNAL_API_KEY`.
- Teste: `GET https://<api>/v1/health` responde 200 sem chave. Qualquer outra rota sem
  `X-Internal-Key` responde 401.

## 4. Projeto da web na Vercel

- Root Directory: `apps/web`, framework Next.js. A Vercel instala o workspace pnpm a partir da raiz.
- Variáveis (Production):
  - `DATABASE_URL` (pooler em modo transação), `INTERNAL_JWT_SECRET`, `INTERNAL_API_KEY`;
  - `API_INTERNAL_URL=https://<api>`;
  - `AUTH_SECRET`, `AUTH_URL=https://<site>`, `SITE_URL=https://<site>`;
  - `ADMIN_EMAILS`, e opcionalmente `AUTH_GOOGLE_ID` e `AUTH_GOOGLE_SECRET`.

## 5. Segredos do GitHub Actions

Em Settings → Secrets and variables → Actions do repositório:

| Segredo | Valor |
|---|---|
| `DATABASE_URL` | Pooler em modo sessão |
| `INTERNAL_JWT_SECRET` | O mesmo da Vercel |
| `WEB_INTERNAL_URL` | `https://<site>` (para revalidar o cache) |
| `BRAPI_TOKEN` | Opcional |

## 6. Migrations

O workflow `Migrations` roda `alembic upgrade head` em todo push na `main` que muda
`apps/api/migrations/`. Para rodar à mão: Actions → Migrations → Run workflow.

## 7. Carga inicial

1. Actions → Worker → Run workflow com `modo=eod`. Com o banco vazio, ele sincroniza o catálogo.
2. Actions → Worker → Run workflow com `modo=backfill`. Pode ser retomado: se passar do
   tempo limite, rode de novo e ele pula os ativos que já têm histórico.

## 8. Conferência

- `/` mostra a faixa de altas e baixas, e `/ativo/PETR4` mostra o gráfico.
- `/admin` (logado com um e-mail de `ADMIN_EMAILS`) lista as execuções do worker.
- `/sitemap.xml` lista os ativos (renova uma vez por dia).

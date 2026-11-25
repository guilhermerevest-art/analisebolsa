# analisebolsa

Site público e gratuito de análise de ativos da B3 (ações, FIIs, ETFs e BDRs):
gráficos, indicadores, fundamentos e proventos, com conteúdo **educacional**.

> Conteúdo educacional. Não é recomendação de investimento.

- Spec da Fase 1: [`docs/superpowers/specs/2026-11-24-fase1-fundacao-design.md`](docs/superpowers/specs/2026-11-24-fase1-fundacao-design.md)
- Plano de implementação: [`docs/superpowers/plans/2026-11-24-fase1-plano.md`](docs/superpowers/plans/2026-11-24-fase1-plano.md)

## Estrutura

```
apps/api/            Python 3.12 (uv): API FastAPI, domínio, fontes de dados e worker EOD
apps/web/            Next.js 15: site, login (Auth.js) e BFF /api/*
packages/api-types/  OpenAPI da API e tipos TypeScript gerados (pnpm gerar)
docs/         specs e planos
```

## Desenvolvimento (apps/api)

```bash
cp .env.example .env
docker compose up -d postgres
cd apps/api
uv sync
uv run alembic upgrade head

# carga inicial de alguns ativos e atualização diária
uv run python -m worker.backfill --tickers PETR4,VALE3 --desde 2020-01-01
uv run python -m worker.eod

# testes (os de banco precisam de um database separado)
createdb -h localhost -U postgres analisebolsa_test
DATABASE_URL_TEST=postgresql://postgres:postgres@localhost:5432/analisebolsa_test uv run pytest
uv run ruff check . && uv run ruff format --check .
```

## API

`uv run uvicorn app.main:app --reload` sobe a API em `http://localhost:8000` (documentação em `/docs`).
Ela é interna: no Coolify só a web é pública. Rotas em `/v1`: `health`, `ativos`, `ativos/{ticker}`
(+ `/cotacoes`, `/indicadores`, `/fundamentos`, `/proventos`), `mercado/destaques` e
`admin/execucoes` (exige JWT interno com `role=admin`). Erros seguem a RFC 7807.

Depois de mudar a API, regenere os tipos com `pnpm gerar` em `packages/api-types` (o CI confere
se o `openapi.json` está atualizado).

## Web (apps/web)

```bash
pnpm install          # na raiz do repositório
pnpm dev              # http://localhost:3000 (precisa da API rodando e do .env)
pnpm test && pnpm lint && pnpm build
```

- Login com e-mail e senha (argon2id) e com Google, se `AUTH_GOOGLE_ID` e `AUTH_GOOGLE_SECRET`
  estiverem definidos. A sessão é um JWT em cookie httpOnly.
- `/api/<rota>` repassa para a API interna (`/v1/<rota>`), com o JWT interno quando há sessão.
- `/api/internal/revalidate` é chamado pelo worker no fim do EOD para renovar o cache.
- Imagem Docker: `docker build -f apps/web/Dockerfile .` (a partir da raiz).

## Worker

| Comando | O que faz |
|---|---|
| `python -m worker.eod` | Catálogo (segundas ou banco vazio), cotações, validação, proventos, indicadores, fundamentos (segundas) e revalidação do cache da web. Agendado no Coolify com `0 22 * * 1-5` (UTC). |
| `python -m worker.backfill [--tickers ...] [--desde AAAA-MM-DD]` | Histórico completo. Pode ser retomado: pula ativos que já têm cotações. |

Cada execução fica registrada em `execucoes_job` com status `ok`, `parcial` ou `erro`.

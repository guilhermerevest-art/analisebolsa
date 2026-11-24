# analisebolsa — Fase 1: Fundação (design)

Data: 2026-11-24
Status: aguardando revisão

## 1. Contexto e objetivo

**analisebolsa** é um site público e gratuito que ajuda pessoas a investir na B3. Ele analisa ativos, mostra gráficos, gera insights educacionais, projeta cenários de entrada e saída e faz simulações.

O produto completo tem 8 funcionalidades, entregues em 4 fases. Este documento especifica a **Fase 1 (Fundação)**, o MVP que fica rodando: ingestão de dados EOD, banco de dados, API, autenticação e página do ativo. As fases 2 a 4 aparecem no roadmap (seção 11) e terão specs próprias.

### Decisões do usuário

| Tema | Decisão |
|---|---|
| Público | Produto público, multiusuário |
| Modelo de negócio | Gratuito no início, sem pagamento no MVP |
| Ativos | Só B3: ações, FIIs, ETFs e BDRs |
| Frequência de dados | EOD (fim do dia), um job diário após o pregão |
| Stack | Next.js (web) + Python FastAPI (api e worker) + PostgreSQL |
| Autenticação | Auth.js: e-mail e senha + Google |
| Infraestrutura | VPS Hostinger com Coolify (Docker, Traefik, SSL, deploy via Git) |
| Arquitetura de cálculo | Híbrida: pré-cálculo no EOD e cálculo sob demanda para o que depende do usuário |
| UI | shadcn/ui + Tailwind + componentes do Magic UI |

### Critérios de sucesso da Fase 1

1. O job EOD roda sozinho em dias úteis e mantém cotações, indicadores, proventos e fundamentos atualizados para todos os ativos listados na B3.
2. Qualquer visitante abre `/ativo/PETR4` e vê o gráfico de candles com indicadores, os fundamentos e os proventos. A página carrega em menos de 2 s.
3. O usuário cria conta com e-mail e senha ou com Google, entra e sai.
4. O admin vê o status das execuções do job.
5. O deploy no Coolify sai de um push na branch `main`.

### Restrição regulatória

Recomendar investimentos a terceiros exige registro na CVM (Resolução CVM 20). Por isso:

- Todo conteúdo analítico é **educacional**. A interface usa termos como "cenário", "sinal técnico" e "indicador", e nunca "compre" ou "venda".
- Toda página com análise mostra o aviso: "Conteúdo educacional. Não é recomendação de investimento."
- O sistema não envia ordens a corretoras.

## 2. Arquitetura

```
             Internet
                │ HTTPS (Traefik/Coolify)
          ┌─────▼─────┐
          │   web     │  Next.js 15 — UI, Auth.js, BFF (/api/*)
          └─────┬─────┘
                │ rede interna Coolify, JWT interno 60 s
          ┌─────▼─────┐        ┌──────────────┐
          │   api     │        │   worker     │  mesma imagem da api
          │  FastAPI  │        │  eod/backfill│  scheduled task Coolify
          └─────┬─────┘        └──────┬───────┘
                └──────────┬──────────┘
                     ┌─────▼─────┐
                     │ postgres  │  resource Coolify, backup agendado
                     └───────────┘
```

- **Só a `web` é pública.** A `api` responde apenas na rede interna (`http://api:8000`).
- **Abordagem híbrida de cálculo.** O worker pré-calcula indicadores (e, nas fases seguintes, insights, métricas do screener e níveis de cenário). Simulações, backtest e carteira são calculados sob demanda na `api`, a partir das fases 3 e 4.

## 3. Banco de dados

O Alembic (`apps/api/migrations`) é o **único dono do schema**, inclusive das tabelas do Auth.js. No Next.js, o Drizzle só declara as tabelas para ter tipagem e não gera migrations.

Volume estimado: cerca de 1.000 tickers × 20 anos × 252 pregões ≈ 5 milhões de linhas. Não há particionamento.

```sql
CREATE TABLE ativos (
  ativo_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  ticker        TEXT NOT NULL UNIQUE CHECK (ticker ~ '^[A-Z0-9]{4,6}$'),
  nome          TEXT NOT NULL,
  tipo          TEXT NOT NULL CHECK (tipo IN ('acao','fii','etf','bdr')),
  setor         TEXT,
  segmento      TEXT,
  logo_url      TEXT,
  ativo         BOOLEAN NOT NULL DEFAULT true,
  atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON ativos (tipo) WHERE ativo;
CREATE INDEX ativos_nome_trgm ON ativos USING GIN (nome gin_trgm_ops); -- extensão pg_trgm

CREATE TABLE cotacoes_diarias (
  ativo_id            BIGINT NOT NULL REFERENCES ativos ON DELETE CASCADE,
  data                DATE NOT NULL,
  abertura            NUMERIC(14,4) NOT NULL CHECK (abertura > 0),
  maxima              NUMERIC(14,4) NOT NULL CHECK (maxima > 0),
  minima              NUMERIC(14,4) NOT NULL CHECK (minima > 0),
  fechamento          NUMERIC(14,4) NOT NULL CHECK (fechamento > 0),
  fechamento_ajustado NUMERIC(14,4) NOT NULL CHECK (fechamento_ajustado > 0),
  volume              BIGINT NOT NULL CHECK (volume >= 0),
  PRIMARY KEY (ativo_id, data),
  CHECK (maxima >= minima)
);

CREATE TABLE indicadores_diarios (
  ativo_id    BIGINT NOT NULL REFERENCES ativos ON DELETE CASCADE,
  data        DATE NOT NULL,
  mm20 DOUBLE PRECISION, mm50 DOUBLE PRECISION, mm200 DOUBLE PRECISION,
  mme9 DOUBLE PRECISION, rsi14 DOUBLE PRECISION,
  macd DOUBLE PRECISION, macd_sinal DOUBLE PRECISION, macd_hist DOUBLE PRECISION,
  bb_superior DOUBLE PRECISION, bb_inferior DOUBLE PRECISION,
  atr14 DOUBLE PRECISION, vol_media20 DOUBLE PRECISION,
  PRIMARY KEY (ativo_id, data)
);

CREATE TABLE proventos (
  provento_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  ativo_id       BIGINT NOT NULL REFERENCES ativos ON DELETE CASCADE,
  tipo           TEXT NOT NULL CHECK (tipo IN ('dividendo','jcp','rendimento','bonificacao','desdobramento','grupamento')),
  data_com       DATE NOT NULL,
  data_pagamento DATE,
  valor          NUMERIC(18,8) NOT NULL,  -- R$/cota; para eventos societários, o fator
  UNIQUE (ativo_id, tipo, data_com)
);
CREATE INDEX ON proventos (ativo_id, data_com DESC);

CREATE TABLE fundamentos (
  ativo_id        BIGINT NOT NULL REFERENCES ativos ON DELETE CASCADE,
  data_referencia DATE NOT NULL,
  pl DOUBLE PRECISION, pvp DOUBLE PRECISION, dy_12m DOUBLE PRECISION,
  roe DOUBLE PRECISION, margem_liquida DOUBLE PRECISION,
  div_liq_ebitda DOUBLE PRECISION, vpa DOUBLE PRECISION, lpa DOUBLE PRECISION,
  valor_mercado NUMERIC(20,2),
  extras JSONB NOT NULL DEFAULT '{}',   -- métricas específicas (ex.: vacância de FII)
  PRIMARY KEY (ativo_id, data_referencia)
);

CREATE TABLE execucoes_job (
  execucao_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tipo          TEXT NOT NULL CHECK (tipo IN ('eod','backfill','catalogo','fundamentos')),
  iniciado_em   TIMESTAMPTZ NOT NULL DEFAULT now(),
  finalizado_em TIMESTAMPTZ,
  status        TEXT NOT NULL DEFAULT 'rodando' CHECK (status IN ('rodando','ok','parcial','erro')),
  ativos_ok     INT NOT NULL DEFAULT 0,
  ativos_erro   INT NOT NULL DEFAULT 0,
  detalhes      JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX ON execucoes_job (iniciado_em DESC);
```

**Tabelas do Auth.js:** `users`, `accounts`, `sessions` e `verification_tokens`, no formato do adapter do Drizzle para Postgres. A sessão do usuário é um **JWT criptografado em cookie `httpOnly`**, porque o provider Credentials do Auth.js não suporta sessão no banco. A tabela `sessions` existe só para compatibilidade com o adapter. A tabela `users` ganha:

- `password_hash TEXT`: hash argon2id. Fica nulo para quem entra só com Google.
- `plano TEXT NOT NULL DEFAULT 'free'`.
- `role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user','admin'))`.

**Tipos:** preços ficam em `NUMERIC`, porque são valores exibidos e precisam ser exatos. Indicadores ficam em `DOUBLE PRECISION`, porque são derivados e é o tipo que o pandas usa. O gráfico mostra o `fechamento`; cálculos de retorno usam o `fechamento_ajustado`.

## 4. Ingestão EOD (worker)

**Disparo:** scheduled task do Coolify com cron `0 22 * * 1-5` em UTC (19h em Brasília). Ela executa `python -m worker.eod`.

**Etapas.** Cada etapa grava seu resultado em `execucoes_job`. Em ordem:

1. **Catálogo** (só às segundas, ou quando a tabela está vazia). Sincroniza `ativos` com a lista da fonte: insere tickers novos e marca `ativo=false` nos que sumiram.
2. **Cotações.** Busca o OHLCV dos pregões que faltam desde a última data gravada de cada ativo e grava com `INSERT ... ON CONFLICT (ativo_id, data) DO UPDATE`. Rodar de novo não duplica nada. Em feriado, não há pregão novo e a etapa termina sem fazer nada.
3. **Validação** (`dominio/validacao.py`). Rejeita linhas com preço ≤ 0, `maxima < minima`, `abertura` ou `fechamento` mais de 1% fora do intervalo [minima, maxima] (a tolerância absorve arredondamento da fonte), ou variação diária acima de 50% sem evento societário correspondente. Linhas rejeitadas vão para `detalhes.rejeitadas` e não são gravadas.
4. **Proventos e ajuste.** Faz upsert dos proventos. Quando surge um provento ou evento societário novo para um ativo que já tem histórico, o worker baixa de novo o histórico completo desse ativo, porque a fonte devolve o `fechamento_ajustado` já recalculado.
5. **Indicadores** (`dominio/indicadores.py`, pandas puro, sem lib externa de TA). Recalcula os indicadores a partir de 400 dias corridos antes do primeiro pregão novo, janela suficiente para a MM200, e faz upsert só das datas novas. No backfill, recalcula o histórico inteiro. Os indicadores usam o `fechamento`, o mesmo preço do gráfico, que no Yahoo já vem ajustado por desdobramentos.
6. **Fundamentos** (semanal). Atualiza o snapshot de fundamentos.
7. **Revalidação.** Chama `POST {WEB_INTERNAL_URL}/api/internal/revalidate` com o JWT interno, para que o cache do Next.js seja renovado.

**Backfill:** `python -m worker.backfill [--tickers PETR4,VALE3] [--desde 2005-01-01]`. Baixa o histórico completo e pode ser retomado, porque pula os ativos que já têm histórico. Respeita o rate limit da fonte.

**Fontes**, atrás do protocolo `FonteDados` (`fontes/base.py`):

```python
class FonteDados(Protocol):
    def listar_ativos(self) -> list[AtivoInfo]: ...
    def cotacoes(self, ticker: str, inicio: date, fim: date) -> list[Candle]: ...
    def proventos(self, ticker: str) -> list[Provento]: ...
    def fundamentos(self, ticker: str) -> Fundamentos | None: ...
```

- **`YahooFonte`** é a fonte primária de cotações e proventos, via endpoint chart com sufixo `.SA`. É uma API não oficial, mas entrega o histórico completo sem custo. O `close` já vem ajustado por desdobramentos, e o `adjclose` também por proventos.
- **`BrapiFonte`** cuida do catálogo e dos fundamentos, e é o fallback de cotações. Usa o token `BRAPI_TOKEN`, que é opcional. No plano grátis, o histórico é limitado.
- A ordem das fontes de cotações é configurável em `FONTES_COTACOES` (padrão: `yahoo,brapi`).
- O que uma fonte não oferece, ela devolve vazio. O orquestrador tenta a próxima fonte da cadeia.

**Erros:**

- A falha de um ticker não derruba o job. O ticker entra em `ativos_erro` e o status fica `parcial`.
- HTTP 429 e 5xx têm até 3 tentativas com backoff exponencial.
- Se todas as fontes falharem, o status fica `erro`, e o log aparece no Coolify.

## 5. API (FastAPI)

**Rede:** a API é interna e não tem domínio público no Coolify.

**Autenticação:** a dependency `usuario_opcional()` / `usuario_obrigatorio()` valida o JWT HS256 assinado com `INTERNAL_JWT_SECRET` e exige `exp` de no máximo 60 s. As claims são `sub`, `plano` e `role`. A dependency `exigir_admin()` checa `role == 'admin'`.

**Endpoints (`/v1`):**

| Método | Rota | Acesso | Descrição |
|---|---|---|---|
| GET | `/v1/health` | público | Healthcheck do Coolify; inclui ping no banco |
| GET | `/v1/ativos?busca=&tipo=&pagina=&limite=` | público | Busca por ticker (prefixo) e por nome (trigram) |
| GET | `/v1/ativos/{ticker}` | público | Cadastro, última cotação e variações de 1 dia, 12 meses e no ano |
| GET | `/v1/ativos/{ticker}/cotacoes?inicio=&fim=&periodo=1d\|1w\|1M` | público | Candles; semanal e mensal são agregados no SQL com `date_trunc` |
| GET | `/v1/ativos/{ticker}/indicadores?inicio=&fim=` | público | Série dos indicadores |
| GET | `/v1/ativos/{ticker}/fundamentos` | público | Último snapshot e histórico |
| GET | `/v1/ativos/{ticker}/proventos` | público | Lista e DY por ano |
| GET | `/v1/mercado/destaques` | público | Maiores altas e baixas do último pregão (faixa e landing) |
| GET | `/v1/admin/execucoes?limite=` | admin | Histórico do job |

**Convenções:**

- Preços em JSON saem como string decimal. Datas seguem a ISO 8601.
- Erros seguem a RFC 7807 (`application/problem+json`). Ticker inexistente retorna 404.
- A entrada é validada com Pydantic. O ticker é normalizado para maiúsculas e validado pela regex do schema.
- O OpenAPI é exportado para `packages/api-types` com `openapi-typescript`.

## 6. Web (Next.js)

**Stack:** Next.js 15 (App Router), TypeScript, Tailwind, shadcn/ui, Magic UI, `lightweight-charts` (npm, versão travada), Auth.js v5 com o adapter do Drizzle e argon2.

**Telas:**

1. **`/` — Landing.** Hero com busca. Faixa `marquee` (Magic UI) com as maiores altas e baixas. `bento-grid` com as funcionalidades (as que ainda não existem aparecem como "em breve"). CTA de cadastro.
2. **Busca global.** Paleta de comandos (`Ctrl+K`) no header, com autocomplete via `/api/ativos?busca=`.
3. **`/ativo/[ticker]`** (SSR com `revalidate` e tag `ativo:{ticker}`):
   - **Cabeçalho:** logo, nome, ticker, tipo, setor, preço (`number-ticker`) e variações.
   - **Gráfico:** candles e volume. Períodos 1M, 6M, 1A, 5A e máx. Intervalos D, S e M. Os overlays MM20, MM50, MM200 e Bollinger podem ser ligados e desligados. RSI e MACD ficam em painéis separados. O componente roda só no cliente e busca os dados pelo BFF.
   - **Abas:** Fundamentos (cards e histórico), Proventos (tabela e DY por ano) e Sobre.
   - **Aviso educacional** fixo.
4. **`/entrar`, `/cadastro`:** login com e-mail e senha e com Google. A validação usa zod. A senha precisa ter no mínimo 8 caracteres.
5. **`/conta`:** perfil e opção de sair.
6. **`/admin`:** tabela de `execucoes_job`. Só aparece para `role=admin`.

**BFF:** os route handlers `/api/*` repassam as chamadas para `API_INTERNAL_URL`, anexando o JWT interno quando há sessão. A rota `/api/internal/revalidate` exige o JWT interno e chama `revalidateTag`.

**Animação:** componentes animados do Magic UI ficam restritos à landing, ao cabeçalho de preço e à faixa de cotações. O gráfico e as tabelas ficam estáticos.

**SEO:** a página `/ativo/[ticker]` tem `generateMetadata` e o projeto gera `sitemap.xml` com todos os tickers ativos.

## 7. Repositório

```
analisebolsa/
├── apps/
│   ├── web/                  Next.js
│   └── api/                  FastAPI + worker (pacote Python, gerenciado com uv)
│       ├── app/              main.py, rotas/, deps.py, schemas.py, db.py
│       ├── dominio/          indicadores.py, validacao.py, ajuste.py (puro, sem I/O)
│       ├── fontes/           base.py, brapi.py, yahoo.py
│       ├── worker/           eod.py, backfill.py, repositorio.py
│       ├── migrations/       Alembic
│       ├── tests/
│       └── Dockerfile
├── packages/api-types/
├── docs/superpowers/specs/
├── docker-compose.yml        dev local: postgres + api + web
├── .env.example
└── .github/workflows/ci.yml
```

**Ferramentas:** Python 3.12 com `uv`, `ruff` e `pytest`. Node 22 com `pnpm`, `eslint` e `vitest`. O acesso ao banco na API usa SQLAlchemy 2 (core) com `psycopg` 3.

## 8. Configuração (variáveis de ambiente)

| Variável | Usada por | Descrição |
|---|---|---|
| `DATABASE_URL` | api, worker, web | String de conexão do Postgres |
| `INTERNAL_JWT_SECRET` | api, worker, web | Segredo HS256 com pelo menos 32 bytes |
| `API_INTERNAL_URL` | web | `http://api:8000` no Coolify |
| `WEB_INTERNAL_URL` | worker | URL da web, para revalidar o cache |
| `AUTH_SECRET` | web | Segredo do Auth.js |
| `AUTH_GOOGLE_ID`, `AUTH_GOOGLE_SECRET` | web | OAuth do Google (opcional; sem elas, o botão do Google fica oculto) |
| `BRAPI_TOKEN` | worker | Opcional |
| `ADMIN_EMAILS` | web | Lista separada por vírgula; esses e-mails recebem `role=admin` no cadastro |

**Desenvolvimento:** usar um database separado (`analisebolsa_dev`), nunca o de produção. Se o Postgres do Coolify for exposto para acesso local, deve ter porta pública restrita por IP, senha forte e `sslmode=require`.

## 9. Testes

- **`dominio/`:** testes unitários dos indicadores contra valores de referência calculados à mão ou com uma planilha (RSI, MACD, Bollinger e ATR com séries curtas e conhecidas), da validação e do ajuste por desdobramento.
- **Fontes:** testes com fixtures JSON de respostas reais, sem rede.
- **Worker:** testes de integração com Postgres (container ou `DATABASE_URL_TEST`). Verificam que rodar o job duas vezes não duplica nada, que pregões faltantes são preenchidos e que o status fica `parcial` quando um ticker falha.
- **API:** `httpx.AsyncClient` cobrindo os endpoints, o 404, o JWT (válido, expirado e com assinatura errada) e a rota de admin.
- **Web:** `vitest` para os utilitários (formatação, conversão de candles) e smoke test de build.
- **CI:** lint, testes e build dos dois apps em cada push.

## 10. Fora do escopo da Fase 1

Insights, cenários, screener, carteira, simulador, watchlist, alertas, backtest, pagamentos, dados intraday e ativos fora da B3.

## 11. Roadmap (cada fase terá spec própria)

- **Fase 2 — Análise:** insights por regras (texto educacional pré-calculado no EOD), cenários de entrada e saída (suporte/resistência, stop e alvo por ATR, com o framework do `technical-analyst` e do `exit.py` do day-trader-skill como referência) e screener (filtros sobre uma tabela de métricas pré-calculadas).
- **Fase 3 — Usuário:** carteira (posições, rentabilidade, alocação), simulador de aporte (aporte mensal, reinvestimento de proventos, comparação com CDI e IPCA, Monte Carlo), watchlist e alertas por e-mail avaliados no fim do EOD.
- **Fase 4 — Avançado:** backtest de estratégias por regras, com controle de look-ahead e survivorship bias e custos de transação (skills `backtesting-frameworks` e `backtest-expert`), e dimensionamento de posição (`position-sizer`).

# Deploy em produção (Vercel)

Arquitetura:

| Peça | Onde roda | Como sobe |
|---|---|---|
| web (`apps/web`) | Projeto Vercel `analisebolsa`, região `gru1` | Push na `main` |
| api (`apps/api`) | Projeto Vercel `analisebolsa-api`, função Python (FastAPI), região `gru1` | Push na `main` |
| Postgres | Gerenciado (Supabase em `sa-east-1`) | Migrations pelo workflow `Migrations` |
| worker | GitHub Actions, workflow `Worker`, com as variáveis da Vercel | Cron `0 22 * * 1-5` (19h de Brasília) e sob demanda |

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

## 5. GitHub Actions

Toda a configuração fica na Vercel. Os workflows `Migrations` e `Worker` baixam as
variáveis de produção do projeto `analisebolsa-api` (`vercel env pull`) antes de rodar.

- No repositório (Settings → Secrets and variables → Actions), crie só o segredo
  `VERCEL_TOKEN`, gerado em vercel.com/account/tokens com acesso ao time do projeto.
- No projeto `analisebolsa-api`, além das variáveis da seção 3, ficam as do worker:
  `WEB_INTERNAL_URL=https://<site>` e, opcionalmente, `BRAPI_TOKEN`.
- As variáveis que o worker usa (`DATABASE_URL`, `INTERNAL_JWT_SECRET`, `WEB_INTERNAL_URL`,
  `BRAPI_TOKEN` e as de notificação abaixo) precisam ser do tipo **encrypted**, não **sensitive**: a Vercel não devolve
  o valor de variáveis sensitive, e o workflow falha avisando qual falta.
- Se o time da Vercel obrigar variáveis sensitive em produção, crie o segredo
  `DATABASE_URL` no GitHub (Settings → Secrets and variables → Actions). Os workflows
  usam esse segredo no lugar do valor da Vercel.
- O GitHub Actions só conecta por IPv4. Se o provedor do banco separar as strings, use no
  projeto da api a do pooler que aceita IPv4.

### Notificações dos alertas (push e WhatsApp)

O EOD avalia os alertas e envia por push e por WhatsApp. Canal sem configuração é pulado: os
disparos ficam gravados e saem por ele no primeiro EOD depois da configuração (até 7 dias,
e só os de depois de o usuário ligar o canal). Para testar sem esperar o EOD: Actions →
Worker → Run workflow com `modo=alertas`.

No projeto `analisebolsa-api`, além das variáveis abaixo, defina `SITE_URL=https://<site>`
(os links das mensagens apontam para ele).

#### Push (Web Push)

1. Gere as chaves uma vez (em `apps/api`): `uv run python -m app.notificacao vapid`.
2. Crie no projeto `analisebolsa-api`, como **encrypted**: `VAPID_PUBLIC_KEY`,
   `VAPID_PRIVATE_KEY` e, opcionalmente, `VAPID_CONTATO` (`mailto:voce@dominio` ou a URL do
   site; sem ela, vale o `SITE_URL`).
3. Se o time obrigar variáveis sensitive, crie também o segredo `VAPID_PRIVATE_KEY` no GitHub
   (o worker usa o segredo no lugar do valor da Vercel).

Trocar as chaves invalida todas as inscrições: cada usuário precisa ligar o push de novo.
No iPhone, o push só funciona com o site adicionado à tela de início (iOS 16.4 ou mais novo).

#### WhatsApp pela Evolution API (recomendado: cadastro no /admin)

O site manda os alertas e os códigos de confirmação por uma instância da
[Evolution API](https://doc.evolution-api.com) (v2), que conecta um número pelo WhatsApp Web.
Nada vai em variável de ambiente: a instância é cadastrada no `/admin`, e a API key fica
guardada no banco cifrada com o `INTERNAL_JWT_SECRET` (se ele mudar, cadastre a chave de novo).

1. Suba a Evolution API num servidor seu (Docker) com HTTPS e crie uma instância, por exemplo
   `analisebolsa`. A API key pode ser a da instância ou a global (`AUTHENTICATION_API_KEY`).
2. Entre no `/admin` com um e-mail de `ADMIN_EMAILS`, preencha a URL, o nome da instância e a
   API key, e salve.
3. Se a instância não estiver conectada, o `/admin` mostra o QR code: no celular do número de
   envio, abra WhatsApp → Aparelhos conectados → Conectar um aparelho. A tela confere a
   conexão sozinha a cada 5 segundos.
4. Mande uma mensagem de teste pelo próprio `/admin`.

Cuidados: use um número só para o site (não o seu pessoal). O WhatsApp pode bloquear números
que mandam muitas mensagens pelo WhatsApp Web; por isso há uma pausa de 2 segundos entre
envios (`WHATSAPP_INTERVALO_S`), e só recebe quem confirmou o próprio número com o código.

Com a instância ligada no `/admin`, ela tem prioridade sobre a Cloud API da Meta abaixo.

#### WhatsApp pela Cloud API oficial da Meta (alternativa)

1. Em business.facebook.com, crie (ou use) uma conta empresarial. Em developers.facebook.com,
   crie um app do tipo **Business** e adicione o produto **WhatsApp**.
2. Em WhatsApp → API Setup, adicione o número de envio (um número que **não** esteja em uso
   no WhatsApp comum) e anote o **Phone number ID**. O número de teste da Meta só envia para
   até 5 números cadastrados, bom para testar.
3. Em Business Settings → System users, crie um usuário do sistema com acesso ao app e à
   conta do WhatsApp e gere um token **permanente** com as permissões
   `whatsapp_business_messaging` e `whatsapp_business_management`.
4. No WhatsApp Manager → Message templates, crie os dois modelos em **Portuguese (BR)**:
   - `codigo_verificacao`, categoria **Authentication**, com o botão **Copy code** (o texto
     do corpo é o padrão da Meta).
   - `alertas_disparados`, categoria **Utility**, corpo:
     `Alertas do pregão no analisebolsa: {{1}}. Gerencie em {{2}}. Conteúdo educacional, não é recomendação de investimento.`
     (exemplos para a aprovação: `PETR4 fechou acima de R$ 40,00 em 26/11/2026, a R$ 41,00`
     e `https://<site>/alertas`).
5. Crie no projeto `analisebolsa-api`: `WHATSAPP_PHONE_NUMBER_ID` e `WHATSAPP_TOKEN`
   (**encrypted**). A API usa o token para mandar o código de confirmação; o worker, para os
   alertas. Se o time obrigar variáveis sensitive, crie também o segredo `WHATSAPP_TOKEN` no
   GitHub.
6. Opcionais, se os nomes ou a versão mudarem: `WHATSAPP_MODELO_ALERTAS`,
   `WHATSAPP_MODELO_CODIGO`, `WHATSAPP_IDIOMA` (padrão `pt_BR`) e `WHATSAPP_API_VERSAO`
   (padrão `v23.0`).

A Meta cobra por mensagem de modelo enviada (preço por categoria e país), e limita os envios
diários enquanto a empresa não é verificada.

As variáveis antigas de e-mail (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USUARIO`, `SMTP_SENHA`,
`EMAIL_REMETENTE`) e o segredo `SMTP_SENHA` do GitHub não são mais usados e podem ser apagados.

## 6. Migrations

O workflow `Migrations` roda `alembic upgrade head` em todo push na `main` que muda
`apps/api/migrations/`. Para rodar à mão: Actions → Migrations → Run workflow.

## 7. Carga inicial

1. Actions → Worker → Run workflow com `modo=eod`. Com o banco vazio, ele sincroniza o catálogo.
2. Actions → Worker → Run workflow com `modo=backfill`. Pode ser retomado: se passar do
   tempo limite, rode de novo e ele pula os ativos que já têm histórico.
3. CDI, IPCA e Ibovespa são carregados pelo EOD e pelo backfill. Para carregar só eles,
   use `modo=indices` (continua de onde parou).

## 8. Conferência

- `/` mostra a faixa de altas e baixas, e `/ativo/PETR4` mostra o gráfico.
- `/admin` (logado com um e-mail de `ADMIN_EMAILS`) lista as execuções do worker.
- `/sitemap.xml` lista os ativos (renova uma vez por dia).

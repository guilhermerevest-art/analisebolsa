# analisebolsa — Fase 5: Notificações e carteira completa (design)

Data: 2026-11-26
Status: em desenvolvimento (decisões padrão abaixo; o usuário pode revisar)
Depende de: [Fase 3](2026-11-25-fase3-usuario-design.md), [Fase 4](2026-11-26-fase4-avancado-design.md)

## 1. Objetivo

1. **Alertas por push e WhatsApp, no lugar do e-mail** (pedido do usuário em 2026-11-26).
2. **Importação de operações** pela planilha de negociação da Área do Investidor da B3.
3. **Imposto de renda da carteira:** apuração mensal de ganho de capital, com isenção de
   R$ 20 mil em vendas de ações, compensação de prejuízo e valor do DARF.

### Critérios de sucesso

1. Um usuário liga o push num aparelho e recebe a notificação dos alertas do pregão, no
   mesmo dia, sem e-mail.
2. Um usuário cadastra o WhatsApp, confirma o número com um código e recebe os alertas lá.
3. Ninguém recebe WhatsApp sem ter confirmado o próprio número (sem envio para número de
   terceiros).
4. Falha num canal não impede o outro, e o que falhou volta no EOD seguinte (até 7 dias).
5. Os textos continuam factuais (o teste de linguagem cobre os textos novos).

## 2. Etapa 1: canais de notificação

### 2.1 Push (Web Push, padrão W3C)

- Service worker `/sw.js` no site e manifesto (`/manifest.webmanifest`), para o site poder
  ser instalado. Funciona em Chrome, Edge e Firefox (desktop e Android) e no Safari do
  iPhone a partir do iOS 16.4, **com o site adicionado à tela de início**.
- Chaves VAPID geradas uma vez (`VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`). A pública vai
  para o navegador pela API; a privada só existe no worker.
- Cada aparelho é uma inscrição. Inscrição que o serviço de push dá como expirada (404 ou
  410) é apagada no envio.
- Conteúdo: título "1 alerta disparado" ou "N alertas disparados", corpo com o primeiro
  texto (e "e mais N"), e clique abrindo `/alertas` (ou o ativo, quando é um só).

### 2.2 WhatsApp (WhatsApp Cloud API, da Meta)

- Envio direto pela API oficial da Meta, sem intermediário. Mensagens que a empresa inicia
  precisam de **modelo (template) aprovado** pela Meta, e cada conversa é cobrada pela Meta.
- Dois modelos, em português (`pt_BR`), a criar no WhatsApp Manager:
  - **`codigo_verificacao`** (categoria Autenticação, botão de copiar código): confirma o número.
  - **`alertas_disparados`** (categoria Utilidade), corpo:
    `Alertas do pregão no analisebolsa: {{1}}. Gerencie em {{2}}. Conteúdo educacional, não é recomendação de investimento.`
    `{{1}}` leva os textos do dia separados por "; " (a Meta não aceita quebra de linha em
    variável), cortados em 900 caracteres com "e mais N". `{{2}}` é o link de `/alertas`.
- **Confirmação do número:** o usuário informa o número (DDD + número; +55 por padrão), a
  API envia um código de 6 dígitos pelo modelo de autenticação, válido por 10 minutos, com
  até 5 tentativas e até 5 códigos por dia por conta. Só número confirmado recebe alertas.
  O código é guardado como hash.
- O usuário pode pausar o WhatsApp sem apagar o número, ou remover o número.

### 2.3 Banco (migration `0006`)

```sql
CREATE TABLE push_inscricoes (
  inscricao_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id      TEXT NOT NULL REFERENCES users ON DELETE CASCADE,
  endpoint     TEXT NOT NULL UNIQUE,
  p256dh       TEXT NOT NULL,
  auth         TEXT NOT NULL,
  aparelho     TEXT,                 -- descrição curta do navegador, para a lista
  criado_em    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE whatsapp (
  user_id          TEXT PRIMARY KEY REFERENCES users ON DELETE CASCADE,
  telefone         TEXT NOT NULL,     -- E.164 sem o "+", ex.: 5511987654321
  confirmado_em    TIMESTAMPTZ,
  ativo            BOOLEAN NOT NULL DEFAULT true,
  codigo_hash      TEXT,
  codigo_expira_em TIMESTAMPTZ,
  tentativas       INT NOT NULL DEFAULT 0,
  codigos_dia      INT NOT NULL DEFAULT 0,
  codigos_data     DATE,
  criado_em        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Um envio por disparo e canal; o que falta é reenviado no EOD seguinte (até 7 dias).
CREATE TABLE alertas_envios (
  alerta_id  BIGINT NOT NULL,
  data       DATE NOT NULL,
  canal      TEXT NOT NULL CHECK (canal IN ('email','push','whatsapp')),
  enviado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (alerta_id, data, canal),
  FOREIGN KEY (alerta_id, data) REFERENCES alertas_disparos ON DELETE CASCADE
);
```

`alertas_disparos.enviado_em` sai; o histórico de e-mails enviados vira linhas com
`canal = 'email'`.

### 2.4 Worker

`worker/alertas.py` avalia como antes e, para cada canal configurado, envia os disparos
pendentes daquele canal agrupados por usuário. `worker/notificacao.py` tem `CanalPush`
(biblioteca `pywebpush`) e `CanalWhatsApp` (`httpx` na Graph API). Canal sem configuração é
pulado com aviso no log; os disparos esperam até 7 dias. O SMTP sai.

### 2.5 API

| Método | Rota | Descrição |
|---|---|---|
| GET | `/v1/notificacoes` | Chave VAPID pública, aparelhos com push, WhatsApp (número mascarado, confirmado, ativo) e quais canais o servidor tem configurados |
| POST | `/v1/notificacoes/push` | Registra a inscrição do aparelho (idempotente pelo endpoint) |
| DELETE | `/v1/notificacoes/push/{id}` | Remove um aparelho |
| POST | `/v1/notificacoes/push/teste` | Envia uma notificação de teste para os aparelhos do usuário |
| PUT | `/v1/notificacoes/whatsapp` | Cadastra ou troca o número e envia o código |
| POST | `/v1/notificacoes/whatsapp/confirmar` | Confirma com o código |
| PATCH | `/v1/notificacoes/whatsapp` | Pausa ou retoma |
| DELETE | `/v1/notificacoes/whatsapp` | Remove o número |

Os disparos em `/v1/alertas` passam a trazer `canais`: onde cada um já foi entregue. A
exportação da conta inclui os aparelhos e o número.

### 2.6 Web

Em `/alertas`, a seção "Onde avisar" com o push (ligar neste aparelho, enviar teste,
lista de aparelhos) e o WhatsApp (número, código, pausar, remover). Os textos de e-mail saem
do site.

## 3. Etapa 2: importação de operações (B3)

**Entregue.** Upload do arquivo "Negociação" da Área do Investidor (Extratos → Negociação, `.xlsx`, até 2 MB e 5.000 linhas), em `/carteira/importar`.
Mapeia data, tipo (compra/venda), código (tirando o sufixo `F` do fracionário), quantidade e
preço; mostra uma prévia com o que vai entrar, o que já existe (mesma data, ativo, tipo,
quantidade e preço) e o que tem ativo desconhecido; o usuário confirma. Custos ficam em zero
(a planilha não traz), editáveis depois.

## 4. Etapa 3: imposto de renda

Apuração mensal por carteira a partir das operações: ações (swing trade 15%, isenção quando
as vendas de ações do mês somam até R$ 20 mil), FIIs (20%, sem isenção) e ETFs (15%, sem
isenção); BDRs como ações sem isenção. Prejuízo compensado nos meses seguintes dentro da
mesma categoria; IRRF de 0,005% descontado; DARF código 6015 com vencimento no último dia útil
do mês seguinte e valor mínimo de R$ 10 (abaixo disso acumula). Day trade fica fora. É uma
ferramenta de conta, com aviso de que não substitui a declaração nem um contador.

## 5. Entrega em etapas (um PR cada)

1. Push e WhatsApp nos alertas (seção 2).
2. Importação da planilha da B3 (seção 3).
3. Imposto de renda (seção 4).

## 6. Testes

- **Notificações:** composição dos textos (push e WhatsApp, corte em 900 caracteres);
  envio por canal com falha num deles; inscrição expirada apagada; reenvio só do canal que
  faltou; nenhum envio para WhatsApp não confirmado ou pausado.
- **API:** isolamento entre usuários, código expirado, tentativas e limite diário (429),
  número inválido (422), exportação com os dados novos.
- **Web:** checagem no navegador de `/alertas`, desktop e celular.

## 7. Decisões tomadas por padrão (o usuário pode mudar)

1. O e-mail sai dos alertas (push e WhatsApp no lugar), como pedido.
2. WhatsApp pela API oficial da Meta, sem intermediário (Twilio e similares cobram por cima).
3. Push pelo padrão Web Push no próprio site, sem app nas lojas.
4. Uma mensagem de WhatsApp por usuário por pregão, com todos os disparos.

## 8. Perguntas para o usuário

1. **Conta na Meta.** O WhatsApp exige uma conta empresarial na Meta (Business Manager), um
   número de telefone dedicado ao envio (não pode estar em uso no WhatsApp comum) e a
   aprovação dos dois modelos da seção 2.2. Enquanto a empresa não é verificada, a Meta
   limita os envios. Você já tem essa conta, ou quer que eu detalhe o passo a passo?
2. **Custo.** A Meta cobra por mensagem de modelo enviada (alguns centavos por mensagem no
   Brasil). Os alertas pelo WhatsApp ficam para todos, ou só para um plano pago no futuro?

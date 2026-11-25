# analisebolsa — Fase 3: Usuário (design)

Data: 2026-11-25
Status: aguardando revisão
Depende de: [Fase 1](2026-11-24-fase1-fundacao-design.md), [Fase 2](2026-11-25-fase2-analise-design.md)

## 1. Objetivo

A Fase 3 traz as funcionalidades que dependem do usuário logado, mais o simulador, que é
público. São quatro:

1. **Watchlist.** Lista de ativos acompanhados, com as métricas da Fase 2 numa tabela.
2. **Carteira.** Operações de compra e venda, posições com preço médio, proventos recebidos,
   alocação e rentabilidade comparada ao CDI e ao Ibovespa.
3. **Simulador de aportes.** Aporte inicial e mensal num ativo, com reinvestimento de
   proventos, no período histórico escolhido, comparado ao CDI e ao IPCA. Uma projeção por
   Monte Carlo mostra a faixa de resultados simulados a partir do histórico (ver seção 9).
4. **Alertas por e-mail.** Regras sobre os ativos da watchlist, avaliadas no fim do EOD.

### Critérios de sucesso

1. Um usuário logado adiciona ativos à watchlist pela estrela na página do ativo e vê a
   lista em `/watchlist`.
2. Em `/carteira`, o usuário lança operações e vê posições, preço médio, proventos
   recebidos, alocação por ativo, setor e tipo, e a rentabilidade desde a primeira operação
   contra CDI e Ibovespa.
3. `/simulador` (público) responde em menos de 1 s no servidor para 20 anos de histórico.
4. Os alertas disparados num pregão chegam por e-mail no mesmo dia, uma vez por regra e
   pregão, sem aumentar o EOD em mais de 5 minutos.
5. Nenhum texto gerado contém linguagem de recomendação (o teste de linguagem da Fase 2 passa
   a cobrir os textos de alerta e do simulador).

### Restrição regulatória (reforço)

- A carteira e o simulador mostram números do passado ou simulações, sempre com o aviso de
  que rentabilidade passada não garante resultado futuro.
- O simulador não sugere ativo nem alocação. O Monte Carlo aparece como "faixa de resultados
  simulados", sem textos de chance ou probabilidade, e com a explicação do método ao lado.
- Os alertas descrevem o fato ("PETR4 fechou acima de R$ 40,00"), nunca uma ação.

## 2. Banco de dados

Uma migration nova (`0003_usuario`). Toda tabela de usuário referencia `users(id)` com
`ON DELETE CASCADE`, para que excluir a conta apague tudo (LGPD).

```sql
-- Séries econômicas e índices (CDI e IPCA do Banco Central, Ibovespa do Yahoo).
CREATE TABLE indices (
  serie  TEXT NOT NULL CHECK (serie IN ('cdi','ipca','ibov')),
  data   DATE NOT NULL,
  valor  DOUBLE PRECISION NOT NULL,  -- cdi: taxa diária em %; ipca: variação mensal em %; ibov: pontos
  PRIMARY KEY (serie, data)
);

CREATE TABLE watchlist (
  user_id   TEXT NOT NULL REFERENCES users ON DELETE CASCADE,
  ativo_id  BIGINT NOT NULL REFERENCES ativos ON DELETE CASCADE,
  criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, ativo_id)
);

CREATE TABLE carteiras (
  carteira_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id     TEXT NOT NULL REFERENCES users ON DELETE CASCADE,
  nome        TEXT NOT NULL CHECK (length(nome) BETWEEN 1 AND 60),
  criado_em   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE operacoes (
  operacao_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  carteira_id BIGINT NOT NULL REFERENCES carteiras ON DELETE CASCADE,
  ativo_id    BIGINT NOT NULL REFERENCES ativos,
  tipo        TEXT NOT NULL CHECK (tipo IN ('compra','venda')),
  data        DATE NOT NULL,
  quantidade  NUMERIC(18,4) NOT NULL CHECK (quantidade > 0),
  preco       NUMERIC(14,4) NOT NULL CHECK (preco > 0),
  custos      NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (custos >= 0),  -- corretagem e taxas
  criado_em   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON operacoes (carteira_id, data);

CREATE TABLE alertas (
  alerta_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id     TEXT NOT NULL REFERENCES users ON DELETE CASCADE,
  ativo_id    BIGINT NOT NULL REFERENCES ativos ON DELETE CASCADE,
  tipo        TEXT NOT NULL CHECK (tipo IN
                ('preco_acima','preco_abaixo','variacao_dia','insight')),
  parametro   DOUBLE PRECISION,  -- preço ou % conforme o tipo
  codigo      TEXT,              -- tipo 'insight': código da regra da Fase 2
  ativo       BOOLEAN NOT NULL DEFAULT true,
  ultimo_disparo DATE,           -- evita repetir no mesmo pregão
  criado_em   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON alertas (ativo_id) WHERE ativo;

CREATE TABLE alertas_disparos (
  alerta_id BIGINT NOT NULL REFERENCES alertas ON DELETE CASCADE,
  data      DATE NOT NULL,
  texto     TEXT NOT NULL,
  enviado_em TIMESTAMPTZ,       -- null enquanto o e-mail não sai
  PRIMARY KEY (alerta_id, data)
);
```

**Limites por usuário** (plano `free`): 100 ativos na watchlist, 5 carteiras, 2.000 operações
por carteira e 30 alertas ativos. A API devolve 409 com mensagem clara ao passar do limite.

## 3. Cálculo (`dominio/`, puro)

### 3.1 `dominio/carteira.py`

- **Posição e preço médio** pelo método da Receita: compras somam quantidade e custo (preço ×
  quantidade + custos); vendas reduzem a quantidade e baixam o custo pelo preço médio, sem
  mudar o preço médio. O resultado realizado de cada venda é (preço − PM) × quantidade − custos.
- **Eventos:** desdobramento, grupamento e bonificação (da tabela `proventos`) ajustam a
  quantidade e o preço médio a partir da data-com, como no ajuste de cotações da Fase 1.
- **Proventos recebidos:** para cada dividendo, JCP ou rendimento, quantidade em custódia no
  fim da data-com × valor. JCP aparece bruto, com nota de que há IR retido na fonte.
- **Rentabilidade:** série diária do patrimônio (quantidades × fechamento) e retorno ponderado
  pelo tempo (TWR), que neutraliza aportes e retiradas. Proventos entram como caixa recebido.
  A mesma série acumulada é calculada para CDI e Ibovespa desde a primeira operação.
- **Alocação:** valor atual por ativo, setor e tipo.

### 3.2 `dominio/simulador.py`

- **Histórico:** compra no primeiro pregão de cada mês, com o valor do aporte, ao fechamento
  ajustado só por eventos; proventos pagos são reinvestidos no pregão seguinte (opção ligada
  por padrão). Mostra patrimônio, total aportado e proventos recebidos mês a mês, e os mesmos
  aportes aplicados no CDI e corrigidos pelo IPCA (poder de compra).
- **Monte Carlo:** 2.000 trajetórias por bootstrap em blocos de 12 meses dos retornos mensais
  totais do próprio ativo (no mínimo 5 anos de histórico; abaixo disso o bloco não aparece).
  Mostra as faixas dos percentis 10, 50 e 90 do patrimônio. Semente fixa por entrada, para o
  mesmo pedido dar o mesmo gráfico.
- Sem ativo, só CDI e IPCA (útil para comparar renda fixa).

### 3.3 `dominio/alertas.py`

Avalia cada alerta ativo contra o pregão do dia: preço de fechamento acima ou abaixo do
parâmetro, variação do dia acima do parâmetro em módulo, ou insight da Fase 2 com o código
escolhido gerado hoje. Devolve o texto fixo do disparo.

## 4. Worker

- **`worker/indices.py`:** CDI (SGS 12) e IPCA (SGS 433) pela API pública do Banco Central, e
  Ibovespa (`^BVSP`) pelo Yahoo. Roda no EOD; o backfill carrega desde 2005.
- **Fim do EOD:** avalia os alertas dos ativos com pregão novo, grava `alertas_disparos` e
  envia um e-mail por usuário com todos os disparos do dia. Falha no envio não derruba o
  job; o disparo fica com `enviado_em` nulo e é reenviado no próximo EOD.
- **E-mail:** um módulo `notificacao/email.py` atrás de uma interface simples, com envio pela
  API do provedor escolhido (seção 9). Sem a chave configurada, os alertas são avaliados e
  gravados, mas não enviados (o log avisa).

## 5. API

Rotas de usuário exigem `usuario_obrigatorio()` e só enxergam dados do próprio `sub`.

| Método | Rota | Acesso | Descrição |
|---|---|---|---|
| GET/PUT/DELETE | `/v1/watchlist`, `/v1/watchlist/{ticker}` | usuário | Lista com métricas; adicionar e remover |
| GET/POST | `/v1/carteiras` | usuário | Listar e criar |
| PATCH/DELETE | `/v1/carteiras/{id}` | usuário | Renomear e excluir |
| GET/POST | `/v1/carteiras/{id}/operacoes` | usuário | Listar e lançar |
| PUT/DELETE | `/v1/carteiras/{id}/operacoes/{op}` | usuário | Editar e excluir |
| GET | `/v1/carteiras/{id}/resumo` | usuário | Posições, proventos, alocação, rentabilidade e comparação |
| GET/POST | `/v1/alertas` | usuário | Listar e criar |
| PATCH/DELETE | `/v1/alertas/{id}` | usuário | Ligar, desligar e excluir |
| GET | `/v1/simulador?ticker=&inicio=&aporte_inicial=&aporte_mensal=&reinvestir=` | público | Histórico e Monte Carlo |
| GET | `/v1/indices/{serie}?inicio=&fim=` | público | Série de CDI, IPCA ou Ibovespa |
| DELETE | `/v1/conta` | usuário | Exclui a conta e todos os dados |

Venda maior que a posição na data é rejeitada com 422 e mensagem que diz a quantidade
disponível.

## 6. Web

1. **Estrela** no cabeçalho da página do ativo (adicionar à watchlist); sem login, leva a
   `/entrar` e volta para a página.
2. **`/watchlist`:** tabela como a do screener, com os ativos da lista, e atalho para criar
   alerta em cada linha.
3. **`/carteira`:** seletor de carteira; cards de patrimônio, custo, resultado, proventos e
   rentabilidade; gráfico da rentabilidade acumulada contra CDI e Ibovespa; tabela de
   posições; rosca de alocação (ativo, setor, tipo); lista de operações com formulário de
   lançamento (ticker com autocomplete, data, quantidade, preço, custos).
4. **`/simulador`:** formulário (ativo opcional, início, aporte inicial e mensal, reinvestir);
   gráfico de patrimônio contra total aportado, CDI e IPCA; tabela anual; bloco de Monte
   Carlo com a explicação do método. Estado na URL para compartilhar.
5. **`/alertas`:** lista e criação de alertas; e-mail de alerta com link para o ativo e
   link para gerenciar alertas.
6. **`/conta`:** exportar meus dados (JSON) e excluir conta.
7. **Header:** itens Watchlist e Carteira para quem está logado. **Landing:** os cards
   Simulador e Alertas deixam de ser "em breve".

As páginas de usuário são dinâmicas e sem cache; `/simulador` é público e cacheado por URL.

## 7. Entrega em etapas (um PR cada)

1. **Índices e watchlist:** migration `0003`, `worker/indices.py` no EOD e no backfill,
   `/v1/indices`, `/v1/watchlist`, estrela, `/watchlist` e itens do header.
2. **Carteira:** `dominio/carteira.py` (posição, PM, eventos, proventos, alocação), rotas de
   carteiras e operações, `/carteira` sem o gráfico de rentabilidade.
3. **Rentabilidade da carteira:** TWR, série contra CDI e Ibovespa, gráfico e cards.
4. **Simulador:** `dominio/simulador.py`, `/v1/simulador`, `/simulador`, card na landing.
5. **Alertas e conta:** `dominio/alertas.py`, envio de e-mail no fim do EOD, `/alertas`,
   exportar e excluir conta, card na landing.

## 8. Testes

- **Carteira:** preço médio com compras e vendas parciais, venda acima da posição,
  desdobramento e grupamento no meio do período, proventos pela custódia na data-com, TWR
  contra um caso calculado à mão com aporte no meio do período.
- **Simulador:** aportes mensais num ativo de preço constante com dividendo conhecido;
  CDI com taxa fixa contra a fórmula fechada; Monte Carlo reprodutível com a mesma semente.
- **Alertas:** cada tipo dispara e não dispara; não repete no mesmo pregão; reenvio do que
  falhou.
- **Índices:** fixtures reais do SGS e do Yahoo, sem rede.
- **API:** isolamento entre usuários (um usuário nunca lê nem altera dados de outro),
  limites (409), validação (422) e exclusão de conta em cascata.
- **Linguagem:** o teste da Fase 2 passa a gerar os textos de alerta e do simulador.
- **Web:** utilitários e checagem no navegador de cada página nova, no desktop e no celular.

## 9. Perguntas para o usuário

1. **E-mail dos alertas.** Recomendo o **Resend** (gratuito até 3.000 e-mails por mês, API
   simples). Ele exige um **domínio próprio** verificado para mandar para qualquer pessoa;
   sem domínio, só manda para o e-mail do dono da conta. Você tem (ou quer registrar) um
   domínio para o site? Se não, a alternativa é SMTP do Gmail com senha de app (até cerca de
   500 por dia, sem domínio).
2. **Monte Carlo no simulador.** Mostrar a faixa de resultados simulados (percentis 10, 50 e
   90) com a explicação do método, como na seção 3.2, ou deixar o simulador só com o
   histórico, já que as faixas podem ser lidas como previsão?
3. **Importação de operações** por planilha da B3 (extrato de negociação da Área do
   Investidor) ficou fora desta fase. Quer que entre como etapa 6?

## 10. Fora do escopo

Importação automática da B3, imposto de renda (DARF, isenção de R$ 20 mil), renda fixa e
fundos na carteira, alertas por push ou WhatsApp, carteiras compartilhadas e planos pagos.

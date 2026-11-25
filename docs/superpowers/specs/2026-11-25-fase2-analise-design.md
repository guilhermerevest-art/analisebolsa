# analisebolsa — Fase 2: Análise (design)

Data: 2026-11-25
Status: aguardando revisão
Depende de: [Fase 1](2026-11-24-fase1-fundacao-design.md)

## 1. Objetivo

A Fase 2 transforma os dados da Fase 1 em análise. São três funcionalidades:

1. **Screener.** Filtrar e ordenar todos os ativos por métricas técnicas e fundamentalistas.
2. **Insights.** Frases educacionais curtas, geradas por regras, que explicam o que os
   indicadores de um ativo mostram hoje ("o preço cruzou a MM200 para cima há 3 pregões").
3. **Cenários.** Suportes e resistências calculados, e cenários de alta, lateral e baixa
   com nível de gatilho, alvo e nível de invalidação baseado no ATR.

Tudo é **pré-calculado no EOD**, como previsto na arquitetura híbrida da Fase 1. Nenhuma
dessas telas depende do usuário, então todas são públicas e cacheáveis.

### Critérios de sucesso

1. `/screener` filtra os cerca de 2.000 ativos por qualquer combinação dos filtros da
   seção 5 e responde em menos de 500 ms no servidor.
2. `/ativo/[ticker]` ganha a aba **Análise** com os insights do dia e o cenário. Os níveis
   de suporte e resistência podem ser ligados no gráfico.
3. Os insights, as métricas e os cenários são recalculados no EOD para os ativos com pregão
   novo, sem aumentar o tempo do job em mais de 20%.
4. Nenhum texto gerado contém linguagem de recomendação (teste automatizado, seção 7).

### Restrição regulatória (reforço)

Vale tudo da Fase 1 (Resolução CVM 20). Para a análise, além disso:

- Insights descrevem **o que aconteceu** nos dados, nunca o que fazer. Ex.: "O RSI(14) está
  em 76, acima de 70, faixa que a análise técnica chama de sobrecompra". Nunca "hora de vender".
- Cenários são **condicionais** ("se o preço fechar acima de R$ 42,10…") e mostram sempre o
  nível que invalida o cenário. Não há probabilidades: um percentual de "chance" seria lido
  como previsão, e não temos base estatística validada para ele (o backtest é da Fase 4).
- O screener não tem preset chamado "melhores ações" nem ranking de "oportunidades".

## 2. Banco de dados

Uma migration nova (`0002_analise`). Três tabelas, todas com **uma linha (ou um conjunto)
por ativo, sempre a mais recente**: não guardamos histórico de análise nesta fase.

```sql
-- Snapshot de métricas por ativo, base do screener e dos insights.
CREATE TABLE metricas_ativo (
  ativo_id          BIGINT PRIMARY KEY REFERENCES ativos ON DELETE CASCADE,
  data              DATE NOT NULL,              -- último pregão considerado
  preco             NUMERIC(14,4) NOT NULL,
  var_1d DOUBLE PRECISION, var_1m DOUBLE PRECISION, var_3m DOUBLE PRECISION,
  var_6m DOUBLE PRECISION, var_12m DOUBLE PRECISION, var_ano DOUBLE PRECISION,
  volatilidade_12m  DOUBLE PRECISION,           -- desvio dos retornos diários, anualizado
  drawdown_12m      DOUBLE PRECISION,           -- queda máxima do topo ao fundo em 12 meses
  max_52s NUMERIC(14,4), min_52s NUMERIC(14,4),
  pos_52s           DOUBLE PRECISION,           -- 0 = na mínima, 100 = na máxima de 52 semanas (em pontos percentuais)
  dist_mm50 DOUBLE PRECISION, dist_mm200 DOUBLE PRECISION,  -- (preço / MM) - 1
  rsi14             DOUBLE PRECISION,
  tendencia         TEXT CHECK (tendencia IN ('alta','baixa','lateral')),
  volume_financeiro_20d NUMERIC(20,2),          -- média de preço × volume, em R$
  pregoes           INT NOT NULL,               -- pregões disponíveis no histórico
  -- cópia do último snapshot de fundamentos, para filtrar sem JOIN
  pl DOUBLE PRECISION, pvp DOUBLE PRECISION, dy_12m DOUBLE PRECISION,
  roe DOUBLE PRECISION, margem_liquida DOUBLE PRECISION, div_liq_ebitda DOUBLE PRECISION,
  valor_mercado NUMERIC(20,2),
  atualizado_em     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON metricas_ativo (volume_financeiro_20d DESC);

CREATE TABLE insights (
  ativo_id   BIGINT NOT NULL REFERENCES ativos ON DELETE CASCADE,
  codigo     TEXT NOT NULL,          -- id da regra, ex.: 'cruzamento_mm50_mm200_alta'
  data       DATE NOT NULL,
  categoria  TEXT NOT NULL CHECK (categoria IN
               ('tendencia','momento','volatilidade','volume','fundamentos','proventos')),
  tom        TEXT NOT NULL CHECK (tom IN ('positivo','neutro','atencao')),
  prioridade SMALLINT NOT NULL,      -- ordena a exibição; maior primeiro
  titulo     TEXT NOT NULL,
  texto      TEXT NOT NULL,
  dados      JSONB NOT NULL DEFAULT '{}',   -- números usados no texto, para a UI e para auditoria
  PRIMARY KEY (ativo_id, codigo)
);
CREATE INDEX ON insights (codigo, data DESC);  -- "quem teve cruzamento hoje" (landing)

CREATE TABLE cenarios (
  ativo_id     BIGINT PRIMARY KEY REFERENCES ativos ON DELETE CASCADE,
  data         DATE NOT NULL,
  atr14        DOUBLE PRECISION NOT NULL,
  niveis       JSONB NOT NULL,   -- [{preco, tipo: suporte|resistencia, toques, ultimo_toque}]
  cenarios     JSONB NOT NULL,   -- [{nome: alta|lateral|baixa, gatilho, alvo, invalidacao, texto}]
  atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Volume: cerca de 2.000 linhas em `metricas_ativo` e `cenarios`, e até ~20.000 em
`insights`. Cada EOD regrava só os ativos com pregão novo (`DELETE` + `INSERT` dos insights
do ativo, `UPSERT` nas outras duas).

## 3. Cálculo (worker, `dominio/`)

Três módulos novos, funções puras sobre pandas como os indicadores da Fase 1:

### 3.1 `dominio/metricas.py`

`calcular_metricas(cotacoes, indicadores, fundamentos) -> Metricas`. Variações usam o
`fechamento_ajustado` (retorno total). A **tendência** segue o framework do
`technical-analyst`, em versão objetiva:

- `alta`: preço > MM50 > MM200 e MM200 subindo nos últimos 20 pregões;
- `baixa`: preço < MM50 < MM200 e MM200 caindo nos últimos 20 pregões;
- `lateral`: o resto.

### 3.2 `dominio/insights.py`

Um catálogo de regras. Cada regra é uma função `(contexto) -> Insight | None`, registrada
com `codigo`, `categoria`, `tom` e `prioridade`. Textos em português, com valores
formatados, montados a partir de templates fixos (nada de geração livre).

Regras da primeira versão:

| Código | Dispara quando | Tom |
|---|---|---|
| `cruzamento_mm50_mm200_alta` / `_baixa` | MM50 cruzou a MM200 nos últimos 5 pregões | positivo / atenção |
| `preco_mm200_acima` / `_abaixo` | preço cruzou a MM200 nos últimos 5 pregões | positivo / atenção |
| `distancia_mm200` | preço mais de 20% acima ou abaixo da MM200 | atenção |
| `rsi_sobrecompra` / `rsi_sobrevenda` | RSI(14) > 70 / < 30 | atenção / neutro |
| `macd_cruzamento_alta` / `_baixa` | MACD cruzou a linha de sinal no último pregão | positivo / atenção |
| `maxima_52s` / `minima_52s` | fechamento na máxima / mínima de 52 semanas | positivo / atenção |
| `bollinger_compressao` | largura das bandas no menor nível de 6 meses | neutro |
| `bollinger_rompimento` | fechamento fora das bandas | neutro |
| `volume_anormal` | volume do dia > 2,5 × média de 20 pregões | neutro |
| `volatilidade_alta` | volatilidade de 20 pregões > 1,5 × a de 12 meses | atenção |
| `tendencia` | sempre: resume a classificação da seção 3.1 | conforme a tendência |
| `dy_historico` | DY 12m acima da média dos últimos 5 anos do próprio ativo | positivo |
| `pl_setor` | P/L no quartil inferior ou superior do setor (mínimo de 5 pares) | neutro |

O texto explica o conceito em uma frase, porque o público é iniciante. Exemplo de
`cruzamento_mm50_mm200_alta`: título "Cruzamento de médias para cima"; texto "A média de
50 pregões (R$ 38,20) passou para cima da média de 200 (R$ 37,90) há 2 pregões. Na análise
técnica, esse movimento é chamado de *golden cross* e costuma ser lido como sinal de
tendência de alta de prazo mais longo."

### 3.3 `dominio/cenarios.py`

1. **Níveis.** Pivôs (topos e fundos locais) nos candles **semanais** dos últimos 3 anos,
   com janela de 2 semanas de cada lado, como no framework do `technical-analyst` (prazo
   longo pesa mais). Pivôs a menos de 1 × ATR(14) semanal entre si viram um nível só, com
   preço médio. A força do nível é o número de toques. Ficam os até 3 níveis mais fortes
   abaixo do preço (suportes) e acima (resistências), mais a máxima e a mínima de 52 semanas.
2. **Cenários**, a partir do suporte (S1) e da resistência (R1) mais próximos:
   - **Alta:** gatilho = fechamento acima de R1; alvo = R2 (ou R1 + 2 × ATR, se não houver
     R2); invalidação = R1 − 1,5 × ATR diário.
   - **Lateral:** preço entre S1 e R1; os dois são os limites.
   - **Baixa:** gatilho = fechamento abaixo de S1; alvo = S2 (ou S1 − 2 × ATR);
     invalidação = S1 + 1,5 × ATR diário.
   - Cada cenário mostra a distância percentual até gatilho, alvo e invalidação, e a relação
     entre as duas distâncias. Não mostra probabilidade (seção 1).

### Elegibilidade

Insights técnicos e cenários só são gerados para ativos com pelo menos 200 pregões e volume
financeiro médio de 20 dias de pelo menos R$ 100 mil. Abaixo disso, a aba Análise mostra
"Dados insuficientes para análise técnica confiável" e explica o motivo. As métricas do
screener são calculadas para todos.

### Worker

O EOD ganha três etapas depois de **Indicadores** e antes de **Revalidação**:
métricas → insights → cenários, só para os ativos com pregão novo ou fundamentos novos.
Novo comando `python -m worker.analise [--tickers ...]`, que recalcula a análise sem buscar
dados (usado depois do backfill e quando uma regra muda). O workflow `Worker` ganha o modo
`analise`.

## 4. API

| Método | Rota | Descrição |
|---|---|---|
| GET | `/v1/ativos/{ticker}/analise` | Métricas, insights ordenados por prioridade e cenário. 200 com `elegivel=false` quando não há análise |
| GET | `/v1/screener?filtros…&ordem=&pagina=&limite=` | Ativos que passam nos filtros, com as métricas |
| GET | `/v1/screener/campos` | Metadados dos filtros: nome, rótulo, unidade, faixa observada. A UI monta o formulário a partir dele |
| GET | `/v1/mercado/sinais` | Contagem e exemplos dos insights do dia por código (para a landing) |

**Filtros do screener**, em lista fechada (nada de SQL vindo do cliente): `tipo`, `setor`,
`tendencia`, e faixas `campo_min` / `campo_max` para `preco`, `var_1m`, `var_12m`,
`volatilidade_12m`, `pos_52s`, `dist_mm200`, `rsi14`, `volume_financeiro_20d`, `pl`, `pvp`,
`dy_12m`, `roe`, `margem_liquida`, `div_liq_ebitda` e `valor_mercado`. Ordenação por
qualquer um desses campos. `limite` até 100. O SQL é montado com parâmetros sobre
`metricas_ativo JOIN ativos`, que é pequeno o suficiente para não precisar de índice por
campo.

## 5. Web

1. **`/ativo/[ticker]`, aba Análise** (a primeira aba):
   - card de **tendência** (alta / baixa / lateral) com a explicação;
   - lista de **insights** agrupados por categoria, com ícone de tom;
   - card de **cenários**: os três cenários com gatilho, alvo, invalidação e distâncias;
   - no gráfico, um botão **Níveis** desenha suportes e resistências como `priceLine`.
2. **`/screener`:**
   - filtros na lateral (no celular, em gaveta), estado na URL para poder compartilhar;
   - tabela ordenável com ticker, nome, preço, variações, tendência, DY, P/L e liquidez,
     com paginação no servidor;
   - presets descritivos: "Perto da máxima de 52 semanas", "Perto da mínima de 52 semanas",
     "Tendência de alta", "Dividend yield acima de 6%", "Baixa volatilidade", "Mais
     negociados". Todos são só combinações de filtros, visíveis e editáveis;
   - filtro padrão de liquidez mínima (R$ 100 mil por dia), que o usuário pode remover.
3. **Landing:** os cards Screener, Insights e Cenários do bento grid deixam de ser "em
   breve". Nova faixa "Sinais de hoje" com contagens de `/v1/mercado/sinais` ("12 ativos
   renovaram a máxima de 52 semanas").
4. **SEO:** `/screener` entra no sitemap; os presets têm URL própria.

## 6. Entrega em etapas (um PR cada)

1. **Métricas e screener:** migration, `dominio/metricas.py`, etapa no worker, `worker.analise`,
   `/v1/screener*`, página `/screener`.
2. **Insights:** `dominio/insights.py` com o catálogo, etapa no worker, `/v1/ativos/{t}/analise`
   (parte de insights), aba Análise.
3. **Cenários:** `dominio/cenarios.py`, etapa no worker, card de cenários e botão Níveis no
   gráfico.
4. **Landing e acabamento:** `/v1/mercado/sinais`, faixa "Sinais de hoje", bento grid, sitemap.

## 7. Testes

- **Métricas:** séries sintéticas com resultado conhecido (variação, volatilidade, drawdown,
  posição em 52 semanas, classificação de tendência).
- **Insights:** cada regra com um caso que dispara e um que não dispara; textos com números
  formatados em pt-BR.
- **Linguagem:** teste que gera todos os textos possíveis do catálogo e falha se aparecer
  "compre", "venda", "recomend", "oportunidade", "garantid" ou "lucro certo".
- **Cenários:** série com topos e fundos plantados; confere os níveis, a fusão de pivôs
  próximos e os cálculos de gatilho, alvo e invalidação.
- **API:** filtros, ordenação, paginação e rejeição de campo fora da lista (422).
- **Web:** testes de formatação e do estado de filtros na URL; checagem no navegador do
  screener e da aba Análise.

## 8. Fora do escopo

Histórico de insights, alertas (Fase 3), probabilidades ou backtest dos cenários (Fase 4),
linhas de tendência inclinadas e padrões gráficos (ombro-cabeça-ombro etc.), comparação
entre ativos e exportação do screener para CSV.

## 9. Perguntas para o usuário

1. Cenários **sem probabilidade**, como proposto na seção 1, ou prefere uma indicação
   qualitativa (ex.: "a favor da tendência" / "contra a tendência")?
2. O filtro padrão de liquidez (R$ 100 mil por dia) e o mínimo de 200 pregões para a análise
   técnica estão bons?

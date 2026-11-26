# analisebolsa — Fase 4: Avançado (design)

Data: 2026-11-26
Status: em desenvolvimento (decisões padrão abaixo; o usuário pode revisar)
Depende de: [Fase 1](2026-11-24-fase1-fundacao-design.md), [Fase 2](2026-11-25-fase2-analise-design.md), [Fase 3](2026-11-25-fase3-usuario-design.md)

## 1. Objetivo

Duas ferramentas públicas, educacionais, sem login:

1. **Backtest de estratégias por regras.** O usuário escolhe um ativo, um período e uma
   estratégia de uma lista fechada, com poucos parâmetros, e vê como ela teria se comportado
   no histórico, contra manter o ativo (buy and hold) e contra o CDI, já com custos.
2. **Calculadora de risco e tamanho de posição.** A partir do capital, do risco aceito por
   operação, do preço de entrada e do stop (manual ou por múltiplo do ATR do ativo), mostra a
   quantidade que limita a perda até o stop ao risco escolhido.

### Critérios de sucesso

1. `/backtest` responde em menos de 1 s no servidor para 20 anos de um ativo.
2. Nenhuma decisão do backtest usa dado do futuro (teste dedicado).
3. Os custos (corretagem, emolumentos e deslizamento) aparecem e entram no resultado.
4. O resultado mostra o período dentro e fora da amostra separados, para expor resultados
   que dependem de um trecho só.
5. Nenhum texto gerado tem linguagem de recomendação (o teste de linguagem cobre as duas
   ferramentas).

### Restrição regulatória (reforço)

- O backtest é um exercício sobre o passado: aviso fixo de que resultado simulado não garante
  resultado futuro e de que estratégias ajustadas ao histórico costumam piorar fora dele.
- Sem ranking de estratégias, sem "melhor parâmetro" e sem otimização automática.
- A calculadora não diz o que operar: só faz a conta de risco com os números do usuário.
  Os textos falam em "entrada", "saída", "posição" e "stop".

## 2. Backtest (`dominio/backtest.py`, puro)

### 2.1 Dados

Cotações diárias do banco. Para incluir proventos sem viés, todos os preços (abertura,
máxima, mínima e fechamento) são multiplicados pelo fator de ajuste do dia
(`fechamento_ajustado / fechamento`), o que equivale a reinvestir os proventos.

### 2.2 Estratégias (lista fechada)

| Código | Entrada | Saída | Parâmetros (limites) |
|---|---|---|---|
| `cruzamento_mm` | MM curta cruza a longa para cima | cruza para baixo | curta 5–100, longa 20–250, curta < longa |
| `rsi` | IFR de P pregões fecha abaixo de X | IFR fecha acima de Y | P 2–30, X 5–50, Y 50–95 |
| `macd` | MACD cruza a linha de sinal para cima | cruza para baixo | rápida 5–50, lenta 10–100, sinal 3–30 |
| `bollinger` | fechamento abaixo da banda inferior | fechamento acima da média | período 10–50, desvios 1–3 |
| `setup_91` | MME vira para cima | MME vira para baixo | período 5–50 |
| `rompimento` | fechamento acima da máxima dos N pregões anteriores | fechamento abaixo da mínima dos M anteriores | N 10–250, M 5–100 |
| `buy_and_hold` | primeiro pregão | nunca | — |

**Estratégias prontas** (pedido do usuário em 2026-11-26): atalhos na página que preenchem a
regra e os parâmetros: Golden cross (50/200), Cruzamento 9/21, IFR2 (2, 10, 70), IFR clássico
(14, 30, 70), Setup 9.1, MACD (12, 26, 9), Bollinger (20, 2), Tartarugas 20/10 e 55/20, Buy and
hold. Barsi, Magic Formula e Graham ficam fora: dependem de fundamentos na data de cada balanço,
que não temos, e o teste teria viés de look-ahead. Entram depois como filtros prontos do Screener.

Stop opcional por ATR (múltiplo 1–5): sai na abertura seguinte se o fechamento ficar abaixo
de entrada − k × ATR14 da entrada.

### 2.3 Execução sem look-ahead

- O sinal é calculado com dados até o fechamento do pregão `t` e executado na **abertura de
  `t+1`**. O indicador só começa a valer depois do aquecimento (o maior período).
- Só posição comprada, 100% do capital quando posicionado, sem alavancagem. Fora da posição,
  o caixa rende o CDI do dia (opção, ligada por padrão).
- **Custos por execução:** corretagem fixa em R$ (padrão 0), emolumentos e taxas de 0,03% do
  volume e deslizamento de 0,05% contra o usuário (padrões editáveis com limites).

### 2.4 Resultado

Curva do patrimônio (base 100) da estratégia, do buy and hold e do CDI; drawdown; métricas
(retorno total, retorno anual composto, volatilidade anual, drawdown máximo, índice de Sharpe
contra o CDI, tempo posicionado, número de operações, % de operações com resultado positivo,
resultado médio por operação, custos totais); lista das operações; e as mesmas métricas
separadas em **dentro da amostra** (primeiros 70% do período) e **fora da amostra** (últimos
30%). Mínimo de 1 ano de pregões depois do aquecimento.

### 2.5 Vieses (explicados na página)

- **Look-ahead:** evitado pela execução na abertura seguinte (seção 2.3).
- **Sobrevivência:** o catálogo tem os ativos listados hoje; empresas que saíram da bolsa
  não aparecem, o que tende a favorecer resultados. O aviso fica na página.
- **Sobreajuste:** poucos parâmetros, sem otimização, e a divisão dentro/fora da amostra.
- **Custos:** sempre incluídos.

## 3. Calculadora de posição (`dominio/posicao.py`, puro)

Entradas: capital, risco por operação (% do capital, 0,1–5, padrão 1), preço de entrada,
stop (preço, ou múltiplo do ATR14 do ativo quando há ticker), lote (padrão ou fracionário) e
limite de concentração (% do capital por posição, padrão 25%).

Saída: quantidade (arredondada para baixo no lote), valor da posição e % do capital, perda
até o stop em R$ e em % do capital, se o limite de concentração reduziu a quantidade, e os
preços em 1R, 2R e 3R (distância até o stop multiplicada), só como referência de cálculo.

Com ticker, a página preenche o último fechamento e o ATR14 do ativo.

## 4. API

| Método | Rota | Acesso | Descrição |
|---|---|---|---|
| GET | `/v1/backtest?ticker=&estrategia=&inicio=&fim=&...params` | público | Resultado do backtest |
| GET | `/v1/posicao?capital=&risco=&entrada=&stop=&ticker=&atr_mult=&lote=&concentracao=` | público | Cálculo de posição |

Respostas públicas com `Cache-Control: public, max-age=3600`.

## 5. Web

1. **`/backtest`:** formulário (ativo, período, estratégia e seus parâmetros, stop por ATR,
   custos), estado na URL; cards de métricas da estratégia, do buy and hold e do CDI; gráfico
   do preço com as entradas e saídas marcadas e o estado da regra no último pregão (pedido do
   usuário); gráfico do patrimônio (um eixo, base 100) e do drawdown; tabela dentro/fora da amostra; lista de
   operações; bloco sobre vieses; aviso.
2. **`/posicao`:** calculadora com resultado em cards e explicação da conta.
3. Página do ativo: atalhos "Testar estratégia" e "Calcular posição" com o ticker preenchido.
4. Header e landing com as duas ferramentas.

## 6. Entrega em etapas (um PR cada)

1. **Backtest:** domínio, rotas, `/backtest`, atalho na página do ativo, landing.
2. **Posição:** domínio, rota, `/posicao`, atalho na página do ativo.

## 7. Testes

- **Backtest:** série sintética com resultado calculado à mão (uma operação, custos exatos);
  sinal no fechamento executado na abertura seguinte; teste de look-ahead (mudar os dados
  depois de `t` não muda nenhuma decisão até `t`); stop por ATR; caixa no CDI; divisão
  dentro/fora da amostra; validação de parâmetros.
- **Posição:** quantidade por risco, arredondamento por lote, limite de concentração, stop
  acima da entrada (422), ATR.
- **Linguagem:** textos das duas ferramentas.
- **Web:** parser da URL e checagem no navegador, desktop e celular.

## 8. Decisões tomadas por padrão (o usuário pode mudar)

1. Só posição comprada (sem venda a descoberto).
2. Caixa rende CDI fora da posição.
3. Custos padrão: corretagem R$ 0, taxas 0,03%, deslizamento 0,05%.
4. Divisão dentro/fora da amostra em 70/30, sem otimização automática.

## 9. Fora do escopo

Estratégias escritas pelo usuário, carteira com vários ativos no backtest, otimização de
parâmetros, dados intraday, venda a descoberto e opções.

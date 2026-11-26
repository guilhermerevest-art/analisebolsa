/**
 * Glossário em linguagem simples. `curto` aparece na dica (o "?" ao lado de um termo);
 * `longo`, só na página /glossario. Os textos explicam, não sugerem o que fazer.
 */

export type Categoria = "Básico" | "Gráfico e indicadores" | "Fundamentos" | "Risco e retorno" | "Carteira e imposto";

export type Termo = { titulo: string; categoria: Categoria; curto: string; longo?: string };

export const GLOSSARIO = {
  // Básico
  acao: {
    titulo: "Ação",
    categoria: "Básico",
    curto: "Um pedaço de uma empresa negociado na bolsa. Quem tem ações é sócio e pode receber parte do lucro.",
  },
  fii: {
    titulo: "FII (fundo imobiliário)",
    categoria: "Básico",
    curto: "Fundo que investe em imóveis ou títulos do setor, como galpões e shoppings. Costuma distribuir rendimentos todo mês.",
  },
  etf: {
    titulo: "ETF",
    categoria: "Básico",
    curto: "Fundo negociado na bolsa que segue um índice. O BOVA11, por exemplo, acompanha o Ibovespa.",
  },
  bdr: {
    titulo: "BDR",
    categoria: "Básico",
    curto: "Recibo negociado na B3 que representa ações de empresas de fora, como Apple ou Google.",
  },
  ticker: {
    titulo: "Ticker",
    categoria: "Básico",
    curto: "O código do ativo na bolsa, como PETR4. O número final indica o tipo: 3 é ação ordinária, 4 é preferencial, 11 costuma ser unit, FII ou ETF.",
  },
  ibovespa: {
    titulo: "Ibovespa",
    categoria: "Básico",
    curto: "O principal índice da bolsa brasileira: uma média das ações mais negociadas. Serve de régua para o mercado como um todo.",
  },
  cdi: {
    titulo: "CDI",
    categoria: "Básico",
    curto: "A taxa que os bancos usam entre si, quase igual à Selic. É a referência da renda fixa: muitos investimentos rendem uma porcentagem do CDI.",
  },
  ipca: {
    titulo: "IPCA",
    categoria: "Básico",
    curto: "O índice oficial da inflação. Corrigir um valor pelo IPCA mostra quanto ele precisaria valer hoje para manter o mesmo poder de compra.",
  },
  liquidez: {
    titulo: "Liquidez",
    categoria: "Básico",
    curto: "Quanto dinheiro o ativo movimenta por dia. Com pouca liquidez, pode ser difícil negociar sem mexer no preço.",
  },
  proventos: {
    titulo: "Proventos",
    categoria: "Básico",
    curto: "Dinheiro que a empresa ou o fundo paga a quem tem o ativo: dividendos, juros sobre capital próprio (JCP) e rendimentos.",
  },
  data_com: {
    titulo: "Data com",
    categoria: "Básico",
    curto: "O último dia para ter o ativo e receber um provento anunciado. Quem entra depois dessa data não recebe aquele pagamento.",
  },

  // Gráfico e indicadores
  candle: {
    titulo: "Candle",
    categoria: "Gráfico e indicadores",
    curto: "Cada barrinha do gráfico mostra um período: abertura, máxima, mínima e fechamento. Verde quando fechou acima da abertura, vermelho quando fechou abaixo.",
  },
  mm: {
    titulo: "Média móvel (MM)",
    categoria: "Gráfico e indicadores",
    curto: "A média dos últimos fechamentos (20, 50 ou 200 pregões). Suaviza o sobe e desce e ajuda a ver a direção do preço.",
  },
  bollinger: {
    titulo: "Bandas de Bollinger",
    categoria: "Gráfico e indicadores",
    curto: "Uma média de 20 pregões com uma faixa acima e outra abaixo, a 2 desvios. Quando o preço sai da faixa, ele se afastou mais que o normal da média.",
  },
  rsi: {
    titulo: "RSI (IFR)",
    categoria: "Gráfico e indicadores",
    curto: "Índice de força relativa, de 0 a 100. Acima de 70, as altas recentes foram fortes; abaixo de 30, as quedas foram fortes. Mede o ritmo, não o rumo futuro.",
  },
  macd: {
    titulo: "MACD",
    categoria: "Gráfico e indicadores",
    curto: "Diferença entre duas médias exponenciais (12 e 26 pregões), comparada com a média dela mesma. Os cruzamentos mostram mudanças de ritmo do preço.",
  },
  atr: {
    titulo: "ATR",
    categoria: "Gráfico e indicadores",
    curto: "Amplitude média dos últimos 14 pregões: quanto o ativo costuma oscilar num dia, em reais. Útil para dimensionar stops.",
  },
  tendencia: {
    titulo: "Tendência",
    categoria: "Gráfico e indicadores",
    curto: "Alta quando o preço está acima das médias de 50 e 200 pregões e elas sobem; baixa no contrário; lateral no resto. Descreve o passado recente.",
  },
  posicao_52s: {
    titulo: "Posição em 52 semanas",
    categoria: "Gráfico e indicadores",
    curto: "Onde o preço está entre a mínima (0%) e a máxima (100%) do último ano.",
  },
  suporte_resistencia: {
    titulo: "Suporte e resistência",
    categoria: "Gráfico e indicadores",
    curto: "Faixas de preço onde o ativo parou de cair (suporte) ou de subir (resistência) várias vezes no passado.",
  },
  volume: {
    titulo: "Volume",
    categoria: "Gráfico e indicadores",
    curto: "Quantidade negociada no período. Volume alto mostra que muita gente negociou naquele preço.",
  },

  // Fundamentos
  pl: {
    titulo: "P/L (preço sobre lucro)",
    categoria: "Fundamentos",
    curto: "Preço da ação dividido pelo lucro por ação dos últimos 12 meses. Um P/L de 10 quer dizer que o preço equivale a 10 anos do lucro atual.",
  },
  pvp: {
    titulo: "P/VP (preço sobre valor patrimonial)",
    categoria: "Fundamentos",
    curto: "Preço dividido pelo patrimônio por ação. Abaixo de 1, a bolsa vale a empresa por menos que o patrimônio contábil dela.",
  },
  dy: {
    titulo: "Dividend yield (DY)",
    categoria: "Fundamentos",
    curto: "Proventos pagos nos últimos 12 meses divididos pelo preço atual. Mostra quanto voltou em dinheiro, em porcentagem do preço.",
  },
  roe: {
    titulo: "ROE",
    categoria: "Fundamentos",
    curto: "Lucro dividido pelo patrimônio: quanto a empresa lucra para cada real que os sócios têm nela.",
  },
  margem_liquida: {
    titulo: "Margem líquida",
    categoria: "Fundamentos",
    curto: "Quanto sobra de lucro de cada real vendido, depois de todos os custos e impostos.",
  },
  div_liq_ebitda: {
    titulo: "Dívida líquida / EBITDA",
    categoria: "Fundamentos",
    curto: "Quantos anos da geração de caixa operacional seriam precisos para pagar a dívida. Quanto maior, mais endividada a empresa.",
  },
  vpa: { titulo: "VPA", categoria: "Fundamentos", curto: "Valor patrimonial por ação: o patrimônio contábil da empresa dividido pelo número de ações." },
  lpa: { titulo: "LPA", categoria: "Fundamentos", curto: "Lucro por ação: o lucro dos últimos 12 meses dividido pelo número de ações." },
  valor_mercado: {
    titulo: "Valor de mercado",
    categoria: "Fundamentos",
    curto: "Quanto a bolsa diz que a empresa inteira vale: preço da ação vezes o número de ações.",
  },

  // Risco e retorno
  backtest: {
    titulo: "Backtest",
    categoria: "Risco e retorno",
    curto: "Testar uma regra no histórico: como ela teria se saído no passado, com custos. Não diz como vai se sair daqui para frente.",
  },
  buy_and_hold: {
    titulo: "Manter o ativo (buy and hold)",
    categoria: "Risco e retorno",
    curto: "Ficar com o ativo o tempo todo, sem entrar e sair. É a comparação mais simples para saber se a regra fez diferença.",
  },
  retorno_total: { titulo: "Retorno total", categoria: "Risco e retorno", curto: "Quanto o dinheiro variou do começo ao fim do período, em porcentagem." },
  retorno_anual: {
    titulo: "Retorno ao ano",
    categoria: "Risco e retorno",
    curto: "O retorno total convertido para uma taxa por ano, como se fosse constante. Permite comparar períodos de tamanhos diferentes.",
  },
  volatilidade: {
    titulo: "Volatilidade",
    categoria: "Risco e retorno",
    curto: "Quanto o preço sobe e desce no dia a dia, convertido para o ano. Mais volatilidade é um caminho mais acidentado, para cima e para baixo.",
  },
  queda_maxima: {
    titulo: "Queda máxima (drawdown)",
    categoria: "Risco e retorno",
    curto: "A maior queda desde um topo até um fundo no período. Mostra o pior momento que quem estivesse posicionado teria atravessado.",
  },
  sharpe: {
    titulo: "Índice de Sharpe",
    categoria: "Risco e retorno",
    curto: "Quanto o retorno passou do CDI para cada unidade de oscilação. Abaixo de zero, ficou atrás do CDI; quanto maior, mais retorno por risco assumido.",
  },
  tempo_posicionado: {
    titulo: "Tempo posicionado",
    categoria: "Risco e retorno",
    curto: "Parte do período em que a regra estava com o ativo. No resto, o dinheiro ficou no CDI.",
  },
  operacoes_positivas: {
    titulo: "Operações positivas",
    categoria: "Risco e retorno",
    curto: "Porcentagem das entradas e saídas que terminaram com ganho. Uma regra pode errar mais do que acertar e ainda assim ter ganho no total.",
  },
  dentro_fora_amostra: {
    titulo: "Dentro e fora da amostra",
    categoria: "Risco e retorno",
    curto: "O período é dividido em duas partes. Se a regra só funciona na primeira, o resultado provavelmente foi sorte de um trecho específico.",
  },
  sobreajuste: {
    titulo: "Sobreajuste",
    categoria: "Risco e retorno",
    curto: "Testar parâmetros até achar o que deu certo no passado. O resultado fica bonito no histórico e costuma piorar fora dele.",
  },
  deslizamento: {
    titulo: "Deslizamento",
    categoria: "Risco e retorno",
    curto: "A diferença entre o preço esperado e o preço em que a ordem é executada de verdade. O backtest desconta um pouco em cada operação.",
  },
  stop: {
    titulo: "Stop",
    categoria: "Risco e retorno",
    curto: "O preço em que a posição é encerrada para limitar a perda, definido antes da entrada.",
  },
  risco_operacao: {
    titulo: "Risco por operação",
    categoria: "Risco e retorno",
    curto: "Quanto do capital fica exposto se o stop for atingido. Com 1% de R$ 50 mil, a perda até o stop fica em R$ 500.",
  },
  multiplo_r: {
    titulo: "R (múltiplo do risco)",
    categoria: "Risco e retorno",
    curto: "A distância entre a entrada e o stop. 2R é um movimento de duas vezes essa distância a favor.",
  },
  lote: {
    titulo: "Lote padrão e fracionário",
    categoria: "Risco e retorno",
    curto: "Ações são negociadas em lotes de 100 no mercado padrão. No fracionário (código com F no fim), dá para negociar de 1 em 1.",
  },
  simulacao: {
    titulo: "Faixa de resultados simulados",
    categoria: "Risco e retorno",
    curto: "Milhares de caminhos montados sorteando meses do histórico do ativo. A faixa mostra a variedade de resultados possíveis, não uma previsão.",
  },

  // Carteira e imposto
  preco_medio: {
    titulo: "Preço médio",
    categoria: "Carteira e imposto",
    curto: "Quanto você pagou, em média, por cada unidade, incluindo corretagem e taxas. Pelo método da Receita, as saídas não mudam o preço médio.",
  },
  resultado_aberto: {
    titulo: "Resultado em aberto",
    categoria: "Carteira e imposto",
    curto: "Ganho ou perda das posições que você ainda tem, pelo último fechamento. Só vira ganho ou perda de fato quando a posição é encerrada.",
  },
  resultado_realizado: {
    titulo: "Resultado realizado",
    categoria: "Carteira e imposto",
    curto: "Ganho ou perda das posições já encerradas, pelo preço médio. É sobre ele que se calcula o imposto.",
  },
  rentabilidade_twr: {
    titulo: "Rentabilidade ponderada pelo tempo",
    categoria: "Carteira e imposto",
    curto: "Mede o desempenho dos ativos sem que aportes e retiradas distorçam a conta. É o mesmo método usado por fundos.",
  },
  dividendos: {
    titulo: "Dividendos",
    categoria: "Carteira e imposto",
    curto: "Parte do lucro distribuída aos sócios. Hoje são isentos de imposto de renda para pessoa física.",
  },
  jcp: {
    titulo: "JCP (juros sobre capital próprio)",
    categoria: "Carteira e imposto",
    curto: "Outra forma de a empresa distribuir lucro. Já vem com 15% de imposto retido, e na declaração entra o valor líquido.",
  },
  darf: {
    titulo: "DARF",
    categoria: "Carteira e imposto",
    curto: "A guia para pagar o imposto sobre ganhos na bolsa. Código 6015, com vencimento no último dia útil do mês seguinte ao ganho.",
  },
  isencao_20mil: {
    titulo: "Isenção de R$ 20 mil",
    categoria: "Carteira e imposto",
    curto: "Se o total de vendas de ações no mês ficar em até R$ 20 mil, o ganho com ações daquele mês é isento. Não vale para FIIs, ETFs, BDRs nem day trade.",
  },
  prejuizo_compensar: {
    titulo: "Prejuízo a compensar",
    categoria: "Carteira e imposto",
    curto: "Perdas de meses anteriores que abatem ganhos futuros do mesmo tipo antes de calcular o imposto. Não expiram.",
  },
  irrf: {
    titulo: "IRRF (dedo-duro)",
    categoria: "Carteira e imposto",
    curto: "Imposto retido pela corretora nas saídas: 0,005% nas operações comuns e 1% do ganho no day trade. É descontado do imposto do mês.",
  },
  day_trade: {
    titulo: "Day trade",
    categoria: "Carteira e imposto",
    curto: "Entrar e sair do mesmo ativo no mesmo dia, na mesma corretora. Paga 20% sobre o ganho, sem isenção, e o prejuízo só compensa outro day trade.",
  },
  bens_direitos: {
    titulo: "Bens e Direitos",
    categoria: "Carteira e imposto",
    curto: "Ficha da declaração com o que você tinha em 31 de dezembro, pelo custo de compra, não pelo valor de mercado.",
  },
} as const satisfies Record<string, Termo>;

export type ChaveGlossario = keyof typeof GLOSSARIO;

export const CATEGORIAS: Categoria[] = ["Básico", "Gráfico e indicadores", "Fundamentos", "Risco e retorno", "Carteira e imposto"];

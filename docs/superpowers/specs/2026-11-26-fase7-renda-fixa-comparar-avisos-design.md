# Fase 7: dólar como comparação, comparar ativos, renda fixa e fundos, avisos da carteira

## 7.1 Dólar como comparação
- Rentabilidade da carteira e simulador ganham a série do dólar (PTAX, BCB SGS 1).
- Carteira: variação do dólar desde o início, no gráfico, nos acumulados e na tabela mensal.
- Simulador: cada aporte "vira dólar" na PTAX do dia; o valor é dólares × cotação atual.

## 7.2 Comparar ativos (`/comparar`, `GET /v1/comparar?tickers=&inicio=`)
- 2 a 4 tickers; desconhecidos dão 404 com a lista.
- Desempenho com proventos (fechamento ajustado) em base 100 a partir da primeira data comum.
- Tabela lado a lado das métricas do último pregão, com dicas do glossário.
- Entradas: cabeçalho, rodapé, landing, página do ativo ("Comparar com outros").

## 7.3 Renda fixa e fundos na carteira
- Tabela `investimentos` (migration 0009): CDB, LCI/LCA, Tesouro, debênture, outro e fundo.
- Renda fixa: % do CDI (fator diário), prefixado (252 dias úteis) e IPCA + taxa (meses fechados).
  IR regressivo (22,5/20/17,5/15%); LCI/LCA sempre isentas; resgate usa o valor informado.
- Fundos: cota diária da CVM (`cotas_fundos`, informe diário mensal a partir de 2021). Número de
  cotas informado ou calculado pela cota do dia da aplicação (até 7 dias depois). Valor bruto.
- Worker `worker.fundos`: baixa só os meses sem cota de algum fundo, mais o mês atual e o anterior;
  roda no EOD (junto dos índices) e no modo `indices`.
- API: `GET/POST /v1/carteiras/{id}/investimentos`, `PUT/DELETE .../{investimento_id}`.
- Web: seção "Renda fixa e fundos" na carteira, com totais, patrimônio total e formulário.
- Exportação LGPD inclui os investimentos.

## 7.4 Avisos da carteira
- Tipos: proventos pagos (até 3 dias depois), data com (até 5 dias antes, ativos em carteira),
  DARF vencendo em 7 dias, renda fixa vencendo em 7 dias.
- Só para quem tem push ou WhatsApp pronto. Preferências em `avisos_carteira_pref` (sem linha =
  tudo ligado). Cada aviso tem chave única por usuário (`avisos_carteira`), sai uma vez por canal
  (`avisos_carteira_envios`) e é reenviado até 7 dias se falhar.
- Roda no fim do EOD e no modo `alertas` do worker.
- API: `GET/PUT /v1/alertas/carteira`. Web: seção "Avisos da carteira" em `/alertas`.
- Textos informam datas e valores, sem linguagem de recomendação.

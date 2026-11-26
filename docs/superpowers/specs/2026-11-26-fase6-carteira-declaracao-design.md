# analisebolsa — Fase 6: Carteira completa para o Imposto de Renda (design)

Data: 2026-11-26
Status: entregue (decisões padrão abaixo; o usuário pode revisar)
Depende de: [Fase 5](2026-11-26-fase5-notificacoes-carteira-design.md)

## 1. Objetivo

Pedido do usuário em 2026-11-26 ("faça todas"), a partir das sugestões do fim da Fase 5:

1. **Editar operações** na carteira (antes só dava para excluir), para incluir corretagem
   depois de importar o extrato da B3.
2. **Day trade** separado na apuração do imposto.
3. **Declaração anual:** o que a carteira tem para cada ficha do programa do IRPF.

## 2. Editar operações

Um lápis em cada linha de Operações abre o formulário de lançamento em modo de edição
(`/carteira?c=ID&editar=OP#lancar`), com os valores preenchidos em vírgula decimal, botões
Salvar e Cancelar. Usa o `PUT /v1/carteiras/{id}/operacoes/{op}` que já existia, que recusa
a alteração se alguma venda posterior ficar sem posição.

## 3. Day trade (método da Receita)

Na consolidação da carteira (`dominio/carteira.py`), num dia com compra e venda do mesmo
ativo, a quantidade casada (a menor das duas) é day trade: o resultado sai do custo médio das
compras do dia e do preço médio das vendas do dia, com os custos proporcionais, e a posição e o
preço médio não mudam. O que sobra entra como compra (pelo custo do dia) ou venda comum (pelo
preço médio da posição).

Na apuração (`dominio/imposto.py`):

- 20%, sem isenção, com prejuízo próprio (só compensa ganho de day trade).
- IRRF de 1% sobre o resultado positivo de cada dia, dispensado abaixo de R$ 1,00.
- As vendas de day trade não contam para o limite de R$ 20 mil das ações.
- Day trade de FII fica no grupo dos FIIs (20%, prejuízo de FII).

Decisão padrão: como a carteira não sabe a corretora, toda compra e venda do mesmo ativo no
mesmo dia numa carteira conta como day trade. Quem opera em corretoras diferentes separa
cada uma numa carteira (a página de imposto explica).

## 4. Declaração anual

`GET /v1/carteiras/{id}/declaracao?ano=` (sem ano: o anterior ao atual, mas nunca antes da
primeira operação) e a página `/carteira/declaracao`, com seletor de ano:

- **Bens e Direitos:** um item por ativo com posição em 31/12 do ano anterior ou do ano,
  pelo custo de aquisição (com desdobramentos, grupamentos e bonificações), grupo e código
  (ações 03-01, FIIs 07-03; ETFs e BDRs pedem conferência no programa) e o texto pronto para
  a Discriminação, com botão de copiar. Ativos comprados e vendidos dentro do ano não entram.
- **Rendimentos Isentos:** dividendos e rendimentos de FII pagos no ano, por ativo, e os
  ganhos com ações em meses de vendas até R$ 20 mil.
- **Tributação Exclusiva:** JCP pago no ano, com bruto, IR de 15% e líquido.
- **Renda Variável:** meses com venda e DARFs do ano, com link para o mês a mês.

O ano de um provento é o do pagamento (ou da data-com, quando o pagamento não é conhecido),
com a quantidade em custódia no fim da data-com. O CNPJ das fontes pagadoras não está no
catálogo: a página manda conferir nos informes.

## 5. Testes

- Edição: checagem no navegador (valores preenchidos, salvar, aviso).
- Day trade: consolidação com dia casado parcial nos dois sentidos (resultado e preço médio
  calculados à mão), 20% sem isenção, IRRF de 1%, prejuízo separado, vendas fora dos R$ 20 mil.
- Declaração: bens em 31/12 dos dois anos com desdobramento, item vendido no ano, proventos
  pelo ano do pagamento, JCP com IR, API com isolamento e ano padrão.

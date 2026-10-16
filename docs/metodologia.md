# Metodologia

## Por que grupos e âncora

O Google Trends não devolve volume de buscas. Ele devolve um **índice de 0 a 100** que é relativo a tudo o que entrou na mesma consulta: o maior valor da consulta vira 100 e o resto é proporcional a ele. Duas consultas diferentes **não** podem ser comparadas diretamente.

Como cada consulta aceita no máximo 5 termos e monitoramos 17, os termos foram divididos em grupos, e **todo grupo leva o mesmo termo-âncora: "bolsa família"**. A âncora tem volume alto e estável no Brasil todo, então serve de régua comum:

```
indice_vs_ancora = valor do termo / valor de "bolsa família" no mesmo local × 100
```

Exemplo: em Campinas, `inss = 30` e `bolsa família = 40` → `indice_vs_ancora = 75`. Ou seja, buscaram "inss" 75% do que buscaram "bolsa família". Esse número pode ser comparado entre grupos, entre locais e entre dias.

| Grupo | Termos (+ âncora) |
|---|---|
| G1 | inss, aposentadoria, posto de saúde, creche |
| G2 | ubs, escola pública, bpc loas, merenda escolar |
| G3 | mais médicos, saúde da família, escola em tempo integral, dinheiro direto na escola |
| G4 | brasil sorridente |
| CAND | lula, flávio bolsonaro, bolsonaro |

Os grupos misturam macrotemas de propósito: termos de volume parecido ficam juntos, o que evita que um termo muito grande achate os outros em zero.

### Macrotemas

- **Saúde:** posto de saúde, ubs, mais médicos, saúde da família, brasil sorridente
- **Educação:** escola pública, creche, merenda escolar, dinheiro direto na escola, escola em tempo integral
- **Aposentadoria e renda:** aposentadoria, inss, bpc loas, bolsa família
- **Candidatos:** lula, flávio bolsonaro, bolsonaro

## Recortes geográficos

- **Estados** (`geo=BR`, `region=REGION`): uma linha por UF.
- **Cidades de SP** (`geo=BR-SP`, `region=CITY`, incluindo locais de baixo volume): todas as cidades que o Google devolver; Campinas, Ribeirão Preto, Sorocaba, São José dos Campos e São José do Rio Preto são marcadas em `cidade_alvo`.
- **Buscas relacionadas** (`geo=BR`): Brasil todo. Candidatos com janela de 1 dia (`now 1-d`) para pegar o assunto do dia; temas com 7 dias.

## Como ler os números

- `valor` (0-100): só faz sentido **dentro da mesma consulta, no mesmo dia**.
- `indice_vs_ancora`: compare à vontade entre termos, locais e dias. Acima de 100 = mais buscado que "bolsa família".
- Valor 0 ou vazio = volume abaixo do mínimo que o Google publica. Em cidades pequenas isso é comum e **não** significa zero buscas.
- **Buscas relacionadas, lista "em alta":** `Breakout` = crescimento acima de 5.000%; `+250%` = crescimento no período. São os melhores sinais de assunto novo (ex.: "flávio bolsonaro inss" subindo).
- Janela padrão `now 7-d`: cada coleta diária mostra os últimos 7 dias. A variação de um dia para o outro mostra a tendência; o valor isolado é uma média da semana.

## Limitações

- O Trends é uma amostra das buscas do Google, não uma pesquisa de opinião. Mostra **interesse**, não apoio.
- Termos ambíguos ("creche", "aposentadoria") somam buscas de todo tipo, não só de política.
- Cidades fora de SP não entram no plano padrão, por orçamento. Para outro estado, crie um job copiando `cidades_sp` e troque `geo` (ex.: `BR-MG`). Isso custa 5 buscas/dia.
- Mudar termos ou grupos no meio do período quebra a comparação com os dias anteriores. Se precisar mudar, anote a data.

## Orçamento padrão (16/10 a 24/10/2026)

| Item | Cálculo | Buscas |
|---|---|---|
| Estados | 5 grupos × 9 dias | 45 |
| Cidades de SP | 5 grupos × 9 dias | 45 |
| Relacionadas candidatos | 3 × 9 dias | 27 |
| Relacionadas temas | 14 × 3 coletas (16, 19, 22/10) | 42 |
| **Total previsto** | | **159** |
| Teste inicial | `coletor teste --n 5` | 5 |
| Sobra para imprevistos | 250 − 164 | 86 |

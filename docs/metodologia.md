# Metodologia

## Por que grupos e âncora

O Google Trends não devolve volume de buscas. Ele devolve um **índice de 0 a 100** que é relativo a tudo o que entrou na mesma consulta: o maior valor da consulta vira 100 e o resto é proporcional a ele. Duas consultas diferentes **não** podem ser comparadas diretamente.

Como cada consulta de interesse por região aceita no máximo 5 termos, os temas foram divididos em grupos, e **todo grupo leva o mesmo termo-âncora: "flavio bolsonaro"**. A âncora serve de régua comum e é referência de comparação:

```
indice_vs_ancora = valor do termo / valor de "flavio bolsonaro" no mesmo local × 100
```

Exemplo: em Campinas, `inss = 30` e `flavio bolsonaro = 40` → `indice_vs_ancora = 75`. Esse número pode ser comparado entre grupos, entre locais e entre dias.

| Grupo | Termos (+ âncora) |
|---|---|
| G1 | sus, upa, ubs, posto de saúde |
| G2 | quem criou o sus, prouni, quem criou prouni, fundeb |
| G3 | escola pública, bpc loas, cadúnico, aposentadoria 70 anos |
| G4 | inss |
| CAND | lula, bolsonaro, flavio bolsonaro |
| ATQ_LULA_1 | roberta luchsinger, luchsinger, lulinha, filho do lula |
| ATQ_LULA_2 | filho lula bateu, lula lobista, lula socio, lula vorcaro |
| ATQ_FLAVIO_ORG_1 | 134 milhoes, flavio vorcaro, inimigo do trabalhador, privatizar o sus |
| ATQ_FLAVIO_ORG_2 | lottenberg, flavio 6x1 |
| ATQ_FLAVIO_PUSH_1 | flavio miliciano, flavio ana clara, flavio comando vermelho, bolsonaro miliciano |
| ATQ_FLAVIO_PUSH_2 | armas bolsonaro, inflacao bolsonaro |

Os grupos misturam macrotemas de propósito: termos de volume parecido ficam juntos, o que evita que um termo muito grande achate os outros em zero. A âncora é incluída automaticamente; se ela já estiver listada no grupo (como em `CAND`), aparece apenas uma vez na consulta.

### Macrotemas

- **Saúde:** sus, upa, ubs, posto de saúde, quem criou o sus
- **Educação:** prouni, quem criou prouni, fundeb, escola pública
- **Aposentadoria:** bpc loas, cadúnico, aposentadoria 70 anos, inss
- **Candidatos:** lula, bolsonaro, flávio bolsonaro
- **Ataques a Lula:** roberta luchsinger, luchsinger, lulinha, filho do lula, filho lula bateu, lula lobista, lula socio, lula vorcaro
- **Ataques organizacionais a Flávio:** 134 milhoes, flavio vorcaro, inimigo do trabalhador, privatizar o sus, lottenberg, flavio 6x1
- **Ataques de posicionamento a Flávio:** flavio miliciano, flavio ana clara, flavio comando vermelho, bolsonaro miliciano, armas bolsonaro, inflacao bolsonaro

## Recortes geográficos

- **Estados** (`geo=BR`, `region=REGION`): uma linha por UF.
- **Cidades** (`geo=BR-SP`, `BR-MG`, `BR-PR`, `BR-SC`, `BR-GO`, `region=CITY`, incluindo locais de baixo volume): todas as cidades que o Google devolver em cada estado, para os 11 grupos.
  - Cada cidade é cruzada com `config/cidades_segmentacao.csv` (1.794 cidades: RM SP, interior PR, interior SC, GO, MG) por UF + nome sem acento. Quando bate, a linha recebe `cod_tse`, `recorte`, `segmento`, `porte` e `rank_no_segmento_recorte`, e `cidade_alvo = true`.
  - Campinas, Ribeirão Preto, Sorocaba, São José dos Campos e São José do Rio Preto também ficam com `cidade_alvo = true`, sem dados de segmentação.
  - Cidades que não estão em nenhuma das duas listas ficam com `cidade_alvo = false` (por exemplo, Curitiba e Florianópolis, que estão fora dos recortes de interior).
  - O Google só devolve cidades com volume mínimo de buscas: boa parte das cidades pequenas da segmentação vai aparecer vazia ou não aparecer.
- **Buscas relacionadas** (`geo=BR`): Brasil todo. Candidatos com janela de 1 dia (`now 1-d`) para pegar o assunto do dia; temas com 7 dias.

## Como ler os números

- `valor` (0-100): só faz sentido **dentro da mesma consulta, no mesmo dia**.
- `indice_vs_ancora`: compare entre termos, locais e dias. Acima de 100 = mais buscado que "flavio bolsonaro".
- Valor 0 ou vazio = volume abaixo do mínimo que o Google publica. Em cidades pequenas isso é comum e **não** significa zero buscas.
- **Buscas relacionadas, lista "em alta":** `Breakout` = crescimento acima de 5.000%; `+250%` = crescimento no período. São os melhores sinais de assunto novo (ex.: "flávio bolsonaro inss" subindo).
- Janela padrão `now 7-d`: cada coleta diária mostra os últimos 7 dias. A variação de um dia para o outro mostra a tendência; o valor isolado é uma média da semana.

## Limitações

- O Trends é uma amostra das buscas do Google, não uma pesquisa de opinião. Mostra **interesse**, não apoio.
- As consultas monitoram interesse pelos termos, não necessariamente interesse político. Buscas por "posto de saúde" ou "aposentadoria 70 anos", por exemplo, também podem refletir necessidades e dúvidas práticas.
- Para incluir outro estado, adicione o código (ex.: `BR-BA`) em `geos` do job `cidades`. Cada estado custa 5 buscas/dia.
- Mudar termos ou grupos no meio do período quebra a comparação com os dias anteriores. Se precisar mudar, anote a data.

## Orçamento (plano atual)

| Item | Cálculo | Buscas de 16/10 a 24/10 |
|---|---|---|
| Estados | 11 grupos × 9 dias | 99 |
| Cidades (SP, MG, PR, SC, GO) | 11 grupos × 5 estados × 9 dias | 495 |
| Relacionadas candidatos | 3 × 9 dias | 27 |
| Relacionadas temas | 33 × 3 coletas (16, 19 e 22/10) | 99 |
| **Total** | | **720** |

Por dia: 69 buscas (102 nos dias de buscas relacionadas a temas), acima do limite de 50 por hora configurado. A execução para ao atingir o limite; será necessário rodar novamente na hora seguinte para concluir esses dias.

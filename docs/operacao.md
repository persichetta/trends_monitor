# Operação

## Primeiro uso (uma vez)

1. Configure a chave (`.env` local ou secret `SERPAPI_KEY` no GitHub).
2. `python -m coletor cota` para confirmar que a chave funciona e ver o saldo.
3. `python -m coletor plano` para ver as buscas do dia.
4. `python -m coletor teste --n 5` para gastar só 5 buscas e conferir `data/geo_map.csv`.
5. Se estiver tudo certo, deixe o GitHub Actions rodar todo dia (ou rode `executar`).

## Rotina diária (5 minutos)

1. Confira na aba **Actions** se a execução de hoje ficou verde.
2. Abra `data/log_coletas.csv` e veja se as buscas do dia estão com `status = ok`.
3. Rode `python -m coletor cota` (ou veja o log do workflow) e confira se o saldo bate com o plano.
4. Puxe os CSVs para a planilha ou o painel.

## Status no log

| status | Significado | O que fazer |
|---|---|---|
| `ok` | Coletou e salvou | nada |
| `sem_resultados` | Google não tem volume para essa consulta | normal em termos pequenos; não repete |
| `erro` | Falha pontual (rede, resposta estranha) | rode `executar` de novo: só as que falharam são refeitas |
| `erro_fatal` | Chave inválida ou cota/limite estourado | veja abaixo |

## Problemas comuns

- **"Chave SerpApi inválida (401)"**: confira o secret ou o `.env`, sem espaços nem aspas.
- **"Limite por hora atingido"**: espere a próxima hora e rode de novo. O que já foi coletado não é refeito.
- **"A reserva mínima seria atingida"**: a cota está acabando. Avalie desligar `relacionadas_temas` (o job mais caro) em `config/coletas.yaml`.
- **Workflow não roda no horário**: o agendamento do GitHub pode atrasar até ~1h em horários de pico. Use **Run workflow** para rodar na mão.

## Mudar o plano sem estourar a cota

1. Edite `config/termos.yaml` ou `config/coletas.yaml`.
2. Rode `python -m coletor plano`: a última linha mostra o **total previsto até o fim do período**.
3. Some com o que já foi gasto (`coletor cota`) e confira se fica abaixo de 250 com folga.
4. Rode os testes (`python -m pytest -q`). O teste `test_plano_respeita_orcamento` vai falhar se o total mudar: atualize o número esperado de propósito.

Regras que o próprio script verifica:
- no máximo 4 termos por grupo (+ âncora);
- todo termo precisa de um macrotema;
- grupos usados nos jobs precisam existir.

## Depois de 24/10

O script não coleta nada fora do período. Para encerrar:
1. Desative o workflow (**Actions → … → Disable workflow**).
2. Troque ou apague a chave na SerpApi.
3. Exporte `data/` para o arquivo do projeto.

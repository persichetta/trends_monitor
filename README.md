# serpapi-trends-monitor

Coleta diária de dados do **Google Trends** via [SerpApi](https://serpapi.com/google-trends-api) para o monitoramento de temas (saúde, educação, aposentadoria e renda) e dos candidatos, por **estado** e por **cidade** nos cinco recortes da segmentação (RM São Paulo, interior do PR, interior de SC, Goiás e Minas Gerais).

O plano atual usa **33 buscas por dia (47 nos dias de temas)**, ou **292 buscas de 17/10 a 24/10/2026**. Isso **passa da cota do plano gratuito** da SerpApi (250/mês): para cobrir o período inteiro é preciso um plano pago ou créditos extras. A trava `reserva_minima` (padrão 30) continua ligada e interrompe a coleta se a conta for ficar abaixo disso; para desligar, use `reserva_minima: 0` em `config/coletas.yaml`.

---

## O que é coletado

| Job | O que traz | Frequência | Buscas |
|---|---|---|---|
| `estados` | Interesse por estado (27 UFs) para cada grupo de termos | diária | 5/dia |
| `cidades` | Interesse por cidade em SP, MG, PR, SC e GO, para os 5 grupos; cada cidade da segmentação recebe recorte, segmento, porte e cod_tse | diária | 25/dia |
| `relacionadas_candidatos` | Buscas relacionadas (top e em alta) a Lula, Flávio Bolsonaro e Bolsonaro | diária | 3/dia |
| `relacionadas_temas` | Buscas relacionadas aos 14 termos de tema | a cada 3 dias (16, 19, 22/10) | 14 |

Termos (17): posto de saúde, ubs, mais médicos, saúde da família, brasil sorridente, escola pública, creche, merenda escolar, dinheiro direto na escola, escola em tempo integral, aposentadoria, inss, bpc loas, bolsa família, lula, flávio bolsonaro, bolsonaro.

Detalhes de cada escolha em [`docs/metodologia.md`](docs/metodologia.md).

---

## Estrutura

```
serpapi-trends-monitor/
├── coletor/
│   ├── __main__.py        # linha de comando (cota, plano, teste, executar)
│   ├── cliente.py         # chamadas à SerpApi, tratamento de erros, chave nunca impressa
│   ├── plano.py           # lê config/ e monta as buscas do dia
│   ├── parse.py           # converte as respostas em tabelas
│   └── armazenamento.py   # grava JSON bruto, CSVs e log
├── ingestao/
│   ├── __main__.py         # comando manual de ingestão do GEO_MAP
│   ├── config.py           # credenciais e destino BigQuery
│   ├── geo_map.py          # schema/conversão de geo_map.csv
│   ├── related_queries.py  # schema/conversão de related_queries.csv
│   ├── csv_cursor.py       # leitura incremental e checkpoints
│   ├── bigquery.py         # tabela particionada e carga append
│   ├── servico.py          # serviço de ingestão independente
│   └── rotina.py           # orquestra coletor seguido da ingestão
├── config/
│   ├── termos.yaml        # termos, macrotemas, grupos e âncora
│   ├── coletas.yaml       # jobs, período, orçamento e parâmetros
│   └── cidades_segmentacao.csv  # 1.794 cidades da segmentação (recorte, segmento, porte, cod_tse)
├── data/                  # saídas (criadas na primeira coleta)
├── docs/
│   ├── metodologia.md     # como os dados são comparáveis e como ler
│   └── operacao.md        # rotina, falhas e mudanças sem estourar a cota
├── tests/                 # testes com respostas de exemplo (não gastam cota)
├── .github/workflows/coleta-diaria.yml
├── .env.example
└── requirements.txt
```

---

## Instalação local

Requer Python 3.10+.

```bash
git clone <url-do-repositorio>
cd serpapi-trends-monitor
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # depois edite .env e coloque a chave
```

## Comandos

```bash
python -m coletor cota                     # buscas restantes e renovação (NÃO gasta cota)
python -m coletor plano                    # o que seria coletado hoje (NÃO gasta cota)
python -m coletor plano --data 2026-10-19  # idem para outra data
python -m coletor teste --n 5              # roda só as 5 primeiras buscas do dia
python -m coletor executar                 # coleta completa do dia
python -m coletor executar --somente estados
```

### Ingestão manual do GEO_MAP no BigQuery

A execução do coletor e a ingestão são módulos separados, mas há um comando
manual que os coordena em sequência:

```bash
python -m ingestao executar
```

Esse comando coleta a data de hoje, depois ingere as linhas novas de GEO_MAP.
Para outra data ou para restringir/refazer buscas:

```bash
python -m ingestao executar --data 2026-10-19
python -m ingestao executar --somente estados
python -m ingestao executar --data 2026-10-19 --forcar
```

O comando combinado carrega GEO_MAP e `related_queries.csv` em tabelas separadas.
As cargas também podem ser executadas isoladamente:

```bash
python -m ingestao geo-map
python -m ingestao related-queries
```

Também é possível executar o coletor e as ingestões manualmente e em etapas:
`python -m coletor executar`, seguido de um ou ambos os comandos acima.

O comando de ingestão lê `data/geo_map.csv`, envia apenas as linhas ainda não
carregadas e registra um checkpoint local em `data/ingestao/`. O checkpoint só
avança após a confirmação do job no BigQuery. O arquivo CSV acumulado permanece
intacto; se for truncado ou reescrito, o checkpoint detecta a mudança e reinicia
a leitura.

Configuração BigQuery no `.env` (se `GOOGLE_APPLICATION_CREDENTIALS` já estiver
exportada no ambiente, ela tem precedência):

```dotenv
GOOGLE_APPLICATION_CREDENTIALS=/caminho/absoluto/para/service-account.json
# Opcional: se omitido, o projeto é obtido das credenciais.
# BIGQUERY_PROJECT=seu-project-id
BIGQUERY_DATASET=analise_redes
BIGQUERY_TABLE=gtrends_monitoramento_cidades
BIGQUERY_LOCATION=southamerica-east1
```

A conta de serviço precisa executar jobs no projeto e criar/editar a tabela no
dataset. O script cria as tabelas caso não existam, cada uma com seu schema e
partição diária por `data_coleta`; não executa `MERGE`. GEO_MAP vai para
`gtrends_monitoramento_cidades` e related queries para
`gtrends_monitoramento_temas`. GEO_MAP inclui UF e os atributos de segmentação
(`cod_tse`, `recorte`, `segmento`, `porte` e `rank_no_segmento_recorte`), além
dos campos originais; CSVs antigos sem essas colunas também são aceitos. Cada
linha recebe `hora_ingestao` em UTC. Os checkpoints são locais à máquina e devem
ser preservados junto dos CSVs para que as próximas ingestões continuem do ponto
correto.

Antes de cada coleta, o script consulta a conta (de graça) e para se:
- as buscas restantes ficarem abaixo de `reserva_minima` (padrão 30);
- o limite por hora (50) for atingido;
- a chave for inválida ou a cota acabar.

Rodar o mesmo dia duas vezes **não gasta cota de novo**: buscas já feitas ficam registradas em `data/log_coletas.csv` e são puladas (use `--forcar` só se precisar refazer).

---

## Coleta automática no GitHub Actions

1. Crie o repositório como **privado** e suba estes arquivos.
2. Em **Settings → Secrets and variables → Actions → New repository secret**, crie `SERPAPI_KEY` com a chave.
3. Em **Settings → Actions → General → Workflow permissions**, marque **Read and write permissions** (o workflow grava os dados em `data/`).
4. Pronto: o workflow roda todo dia às 06:47 (Brasília) e faz commit dos dados.
5. Para rodar na hora: aba **Actions → Coleta diária Google Trends → Run workflow** (dá para escolher um job só).

Se a coleta falhar, o workflow fica vermelho e o motivo aparece no log e em `data/log_coletas.csv`.

---

## Saídas (`data/`)

| Arquivo | Uma linha por | Colunas principais |
|---|---|---|
| `geo_map.csv` | local × termo × dia | `data_coleta, job, grupo, geo_busca, resolucao, periodo, local, local_codigo, cidade_alvo, termo, macrotema, eh_ancora, valor, indice_vs_ancora, uf, cod_tse, recorte, segmento, porte, rank_no_segmento_recorte` |
| `related_queries.csv` | consulta relacionada × dia | `data_coleta, job, termo_base, macrotema, lista (top / em alta), posicao, consulta, valor, valor_num` |
| `log_coletas.csv` | busca executada | `data_coleta, horario_utc, busca_id, tipo, status, linhas, search_id, mensagem` |
| `bruto/AAAA-MM-DD/*.json` | resposta original | para auditoria e reprocessamento |

Em `geo_map.csv`, `eh_ancora` e `cidade_alvo` são `true`/`false` (compatíveis com BOOLEAN no BigQuery). Para filtrar só as cidades da segmentação: `segmento <> ''` (ou `cod_tse IS NOT NULL` no BQ). As 5 cidades do interior de SP (Campinas, Ribeirão Preto, Sorocaba, São José dos Campos, São José do Rio Preto) têm `cidade_alvo = true`, mas não fazem parte da segmentação.

Os CSVs abrem direto no Google Sheets, Looker Studio ou BigQuery. Como ler `valor` e `indice_vs_ancora`: veja [`docs/metodologia.md`](docs/metodologia.md#como-ler-os-números).

---

## Segurança

- A chave fica **só** no `.env` (local) ou no secret do GitHub. Nunca no código, em planilhas ou em mensagens.
- O script remove a chave de mensagens de erro e dos JSONs salvos (há teste para isso).
- Use uma conta SerpApi **dedicada** a este projeto e **troque a chave** quando o período acabar.
- **Não use o Playground** do site da SerpApi: cada teste lá consome a mesma cota.
- Os dados do Google Trends são agregados e anônimos; nada aqui identifica pessoas.
- `config/cidades_segmentacao.csv` contém a segmentação da campanha (estratégia). **Mantenha o repositório privado** enquanto esse arquivo estiver nele.

## Testes

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

Os testes usam respostas de exemplo em `tests/fixtures/` e não fazem chamadas reais.

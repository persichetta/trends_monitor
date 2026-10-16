# serpapi-trends-monitor

Coleta diária de dados do **Google Trends** via [SerpApi](https://serpapi.com/google-trends-api) para o monitoramento de temas (saúde, educação, aposentadoria e renda) e dos candidatos, por **estado** e por **cidade**.

Este repositório foi feito para caber no **plano gratuito da SerpApi** (250 buscas/mês, 50/hora): o plano padrão usa **159 buscas** entre 16/10 e 24/10/2026 e para sozinho antes de passar da reserva de segurança.

---

## O que é coletado

| Job | O que traz | Frequência | Buscas |
|---|---|---|---|
| `estados` | Interesse por estado (27 UFs) para cada grupo de termos | diária | 5/dia |
| `cidades_sp` | Interesse por cidade no estado de SP, com marcação de 5 cidades-alvo | diária | 5/dia |
| `relacionadas_candidatos` | Buscas relacionadas (top e em alta) a Lula, Flávio Bolsonaro e Bolsonaro | diária | 3/dia |
| `relacionadas_temas` | Buscas relacionadas aos 14 termos de tema | a cada 3 dias | 14 |

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
├── config/
│   ├── termos.yaml        # termos, macrotemas, grupos e âncora
│   └── coletas.yaml       # jobs, período, orçamento e parâmetros
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
| `geo_map.csv` | local × termo × dia | `data_coleta, job, grupo, geo_busca, resolucao, local, local_codigo, cidade_alvo, termo, macrotema, eh_ancora, valor, indice_vs_ancora` |
| `related_queries.csv` | consulta relacionada × dia | `data_coleta, job, termo_base, macrotema, lista (top / em alta), posicao, consulta, valor, valor_num` |
| `log_coletas.csv` | busca executada | `data_coleta, horario_utc, busca_id, tipo, status, linhas, search_id, mensagem` |
| `bruto/AAAA-MM-DD/*.json` | resposta original | para auditoria e reprocessamento |

Os CSVs abrem direto no Google Sheets, Looker Studio ou BigQuery. Como ler `valor` e `indice_vs_ancora`: veja [`docs/metodologia.md`](docs/metodologia.md#como-ler-os-números).

---

## Segurança

- A chave fica **só** no `.env` (local) ou no secret do GitHub. Nunca no código, em planilhas ou em mensagens.
- O script remove a chave de mensagens de erro e dos JSONs salvos (há teste para isso).
- Use uma conta SerpApi **dedicada** a este projeto e **troque a chave** quando o período acabar.
- **Não use o Playground** do site da SerpApi: cada teste lá consome a mesma cota.
- Os dados do Google Trends são agregados e anônimos; nada aqui identifica pessoas.

## Testes

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

Os testes usam respostas de exemplo em `tests/fixtures/` e não fazem chamadas reais.

"""Criação da tabela particionada e carga append no BigQuery."""
from __future__ import annotations

from typing import Any

from .config import ConfigBigQuery

SCHEMA = (
    ("data_coleta", "DATE"),
    ("job", "STRING"),
    ("grupo", "STRING"),
    ("geo_busca", "STRING"),
    ("resolucao", "STRING"),
    ("periodo", "STRING"),
    ("local", "STRING"),
    ("local_codigo", "STRING"),
    ("cidade_alvo", "STRING"),
    ("termo", "STRING"),
    ("macrotema", "STRING"),
    ("eh_ancora", "BOOL"),
    ("valor", "FLOAT64"),
    ("indice_vs_ancora", "FLOAT64"),
    ("uf", "STRING"),
    ("cod_tse", "INT64"),
    ("recorte", "STRING"),
    ("segmento", "STRING"),
    ("porte", "STRING"),
    ("rank_no_segmento_recorte", "INT64"),
    ("hora_ingestao", "TIMESTAMP"),
)

SCHEMA_RELATED_QUERIES = (
    ("data_coleta", "DATE"),
    ("job", "STRING"),
    ("geo_busca", "STRING"),
    ("periodo", "STRING"),
    ("termo_base", "STRING"),
    ("macrotema", "STRING"),
    ("lista", "STRING"),
    ("posicao", "INT64"),
    ("consulta", "STRING"),
    ("valor", "STRING"),
    ("valor_num", "FLOAT64"),
    ("hora_ingestao", "TIMESTAMP"),
)


def criar_cliente(config: ConfigBigQuery):
    """Cria o cliente usando o JSON indicado, sem imprimir conteúdo sensível."""
    import google.auth
    from google.cloud import bigquery

    credenciais, projeto_credencial = google.auth.load_credentials_from_file(str(config.credenciais))
    projeto = config.projeto or projeto_credencial
    if not projeto:
        raise ValueError("Não foi possível determinar o ID do projeto pelas credenciais; defina BIGQUERY_PROJECT.")
    return bigquery.Client(project=projeto, credentials=credenciais, location=config.regiao)


def _validar_schema_existente(tabela, destino: str, schema) -> set[str]:
    """Valida os campos esperados, permitindo campos extras anuláveis no destino."""
    aliases = {
        "FLOAT": "FLOAT64",
        "DOUBLE": "FLOAT64",
        "BOOLEAN": "BOOL",
        "INTEGER": "INT64",
    }
    campos_existentes = {campo.name: campo for campo in tabela.schema}
    schema_esperado = dict(schema)
    extras_nao_anulaveis = {
        nome: (campo.field_type.upper(), campo.mode.upper())
        for nome, campo in campos_existentes.items()
        if nome not in schema_esperado and campo.mode.upper() != "NULLABLE"
    }
    tipos_incompativeis = {
        nome: (
            aliases.get(campos_existentes[nome].field_type.upper(), campos_existentes[nome].field_type.upper()),
            tipo,
        )
        for nome, tipo in schema_esperado.items()
        if nome in campos_existentes
        and aliases.get(campos_existentes[nome].field_type.upper(), campos_existentes[nome].field_type.upper()) != tipo
    }
    if extras_nao_anulaveis or tipos_incompativeis:
        raise ValueError(
            f"Schema incompatível em {destino}; campos extras não anuláveis={extras_nao_anulaveis}, "
            f"tipos incompatíveis={tipos_incompativeis}."
        )
    return set(campos_existentes)


def _garantir_tabela(client, config: ConfigBigQuery, schema=SCHEMA):
    from google.api_core.exceptions import NotFound
    from google.cloud import bigquery

    destino = f"{client.project}.{config.dataset}.{config.tabela}"
    try:
        tabela = client.get_table(destino)
    except NotFound:
        tabela = bigquery.Table(
            destino,
            schema=[bigquery.SchemaField(nome, tipo) for nome, tipo in schema],
        )
        tabela.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field="data_coleta",
        )
        client.create_table(tabela)
        tabela = client.get_table(destino)

    campos_existentes = _validar_schema_existente(tabela, destino, schema)

    faltantes = [
        bigquery.SchemaField(nome, tipo, mode="NULLABLE")
        for nome, tipo in schema
        if nome not in campos_existentes
    ]
    if faltantes:
        tabela.schema = list(tabela.schema) + faltantes
        tabela = client.update_table(tabela, ["schema"])

    particionamento = tabela.time_partitioning
    if particionamento is None or particionamento.field != "data_coleta":
        raise ValueError(f"A tabela {destino} precisa ser particionada por data_coleta.")
    if (tabela.location or "").casefold() != config.regiao.casefold():
        raise ValueError(f"A tabela {destino} está em {tabela.location}, não em {config.regiao}.")
    return destino


def carregar_linhas(
    client,
    config: ConfigBigQuery,
    linhas: list[dict[str, Any]],
    job_id: str,
    schema=SCHEMA,
):
    """Carrega um lote append-only; um job ID estável torna retries seguros."""
    from google.api_core.exceptions import Conflict
    from google.cloud import bigquery

    destino = _garantir_tabela(client, config, schema)
    job_config = bigquery.LoadJobConfig(
        schema=[bigquery.SchemaField(nome, tipo) for nome, tipo in schema],
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
    )
    tentativa = 0
    while True:
        id_tentativa = job_id if tentativa == 0 else f"{job_id}_retry_{tentativa}"
        try:
            job = client.load_table_from_json(
                linhas,
                destino,
                job_id=id_tentativa,
                job_config=job_config,
                location=config.regiao,
            )
        except Conflict:
            # Se a carga terminou mas o processo caiu antes de gravar o
            # checkpoint, recuperar o mesmo job evita inserir o lote de novo.
            job = client.get_job(id_tentativa, location=config.regiao)
            if not job.error_result:
                break
            tentativa += 1
            if tentativa > 5:
                raise RuntimeError(f"Cinco tentativas de carga falharam para o lote {job_id}.")
            continue
        break
    job.result()
    return job

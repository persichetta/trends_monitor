"""Serviço de ingestão incremental do GEO_MAP."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from dotenv import load_dotenv

from . import bigquery
from .config import RAIZ, carregar_config
from .geo_map import job_id_lote, ler_lote_pendente, salvar_checkpoint
from .related_queries import (
    job_id_lote as job_id_related,
    ler_lote_pendente as ler_related_pendente,
    salvar_checkpoint as salvar_checkpoint_related,
)


def executar_geo_map(
    arquivo: Path | None = None,
    checkpoint: Path | None = None,
) -> int:
    load_dotenv(RAIZ / ".env")
    arquivo = arquivo or RAIZ / "data" / "geo_map.csv"
    checkpoint = checkpoint or RAIZ / "data" / "ingestao" / "geo_map_checkpoint.json"
    lote = ler_lote_pendente(arquivo, checkpoint)
    if not lote.linhas:
        print(f"Sem linhas novas para ingestão em {arquivo}.")
        return 0

    config = carregar_config()
    client = bigquery.criar_cliente(config)
    job = bigquery.carregar_linhas(client, config, lote.linhas, job_id_lote(lote))
    salvar_checkpoint(checkpoint, lote)
    print(
        f"Ingestão concluída: {job.output_rows or len(lote.linhas)} linhas em "
        f"{client.project}.{config.dataset}.{config.tabela}."
    )
    return 0


def executar_related_queries(
    arquivo: Path | None = None,
    checkpoint: Path | None = None,
) -> int:
    load_dotenv(RAIZ / ".env")
    arquivo = arquivo or RAIZ / "data" / "related_queries.csv"
    checkpoint = checkpoint or RAIZ / "data" / "ingestao" / "related_queries_checkpoint.json"
    lote = ler_related_pendente(arquivo, checkpoint)
    if not lote.linhas:
        print(f"Sem linhas novas para ingestão em {arquivo}.")
        return 0

    config = carregar_config()
    config_related = replace(config, tabela=config.tabela_related)
    client = bigquery.criar_cliente(config_related)
    job = bigquery.carregar_linhas(
        client,
        config_related,
        lote.linhas,
        job_id_related(lote),
        schema=bigquery.SCHEMA_RELATED_QUERIES,
    )
    salvar_checkpoint_related(checkpoint, lote)
    print(
        f"Ingestão concluída: {job.output_rows or len(lote.linhas)} linhas em "
        f"{client.project}.{config_related.dataset}.{config_related.tabela}."
    )
    return 0

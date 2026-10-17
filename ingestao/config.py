"""Configuração da ingestão GEO_MAP."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO_CREDENCIAIS_PADRAO = RAIZ / "comite-tecnologia-cd8d159a8330.json"


@dataclass(frozen=True)
class ConfigBigQuery:
    credenciais: Path
    projeto: str | None
    dataset: str
    tabela: str
    tabela_related: str
    regiao: str


def carregar_config() -> ConfigBigQuery:
    credenciais_env = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    credenciais = Path(credenciais_env).expanduser() if credenciais_env else ARQUIVO_CREDENCIAIS_PADRAO
    if credenciais_env and not credenciais.is_absolute():
        credenciais = (RAIZ / credenciais).resolve()
    if not credenciais_env and not credenciais.is_file():
        raise ValueError(
            "Defina GOOGLE_APPLICATION_CREDENTIALS no .env com o caminho do JSON "
            "da conta de serviço do Google Cloud."
        )
    if not credenciais.is_file():
        raise ValueError(f"Arquivo de credenciais não encontrado: {credenciais}")

    return ConfigBigQuery(
        credenciais=credenciais,
        projeto=os.environ.get("BIGQUERY_PROJECT") or None,
        dataset=os.environ.get("BIGQUERY_DATASET", "analise_redes"),
        tabela=os.environ.get("BIGQUERY_TABLE", "gtrends_monitoramento_cidades"),
        tabela_related=os.environ.get("BIGQUERY_RELATED_TABLE", "gtrends_monitoramento_temas"),
        regiao=os.environ.get("BIGQUERY_LOCATION", "southamerica-east1"),
    )

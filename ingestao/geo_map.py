"""Leitura incremental, validação e conversão do CSV geo_map."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .csv_cursor import LotePendente, job_id_lote as _job_id_lote
from .csv_cursor import ler_lote_csv, salvar_checkpoint

CAMPOS_GEO_MAP = (
    "data_coleta",
    "job",
    "grupo",
    "geo_busca",
    "resolucao",
    "periodo",
    "local",
    "local_codigo",
    "cidade_alvo",
    "termo",
    "macrotema",
    "eh_ancora",
    "valor",
    "indice_vs_ancora",
)


def ler_lote_pendente(arquivo: Path, checkpoint: Path) -> LotePendente:
    """Lê somente registros GEO_MAP ainda não confirmados no BigQuery."""
    return ler_lote_csv(arquivo, checkpoint, CAMPOS_GEO_MAP, converter_linha, "geo_map")


def converter_linha(linha: dict[str, str]) -> dict[str, Any]:
    """Converte uma linha do CSV aos tipos explícitos do schema BigQuery."""
    try:
        data = datetime.strptime(linha["data_coleta"], "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"data_coleta inválida: {linha['data_coleta']!r}") from exc

    ancora = linha["eh_ancora"].strip().casefold()
    if ancora not in {"sim", "não", "nao"}:
        raise ValueError(f"eh_ancora deve ser 'sim' ou 'não', recebido: {linha['eh_ancora']!r}")

    saida: dict[str, Any] = {campo: linha[campo] for campo in CAMPOS_GEO_MAP}
    saida["data_coleta"] = data.isoformat()
    saida["eh_ancora"] = ancora == "sim"
    for campo in ("valor", "indice_vs_ancora"):
        try:
            saida[campo] = float(linha[campo]) if linha[campo].strip() else None
        except ValueError as exc:
            raise ValueError(f"{campo} inválido: {linha[campo]!r}") from exc
    saida["hora_ingestao"] = datetime.now(timezone.utc).isoformat()
    return saida


def job_id_lote(lote: LotePendente) -> str:
    return _job_id_lote(lote, "geo_map")

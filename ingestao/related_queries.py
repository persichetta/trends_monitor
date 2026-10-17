"""Leitura incremental e conversão do CSV related_queries."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .csv_cursor import LotePendente, job_id_lote as _job_id_lote
from .csv_cursor import ler_lote_csv, salvar_checkpoint

CAMPOS_RELATED_QUERIES = (
    "data_coleta",
    "job",
    "geo_busca",
    "periodo",
    "termo_base",
    "macrotema",
    "lista",
    "posicao",
    "consulta",
    "valor",
    "valor_num",
)


def ler_lote_pendente(arquivo: Path, checkpoint: Path) -> LotePendente:
    """Lê somente registros related_queries ainda não confirmados no BigQuery."""
    return ler_lote_csv(
        arquivo,
        checkpoint,
        CAMPOS_RELATED_QUERIES,
        converter_linha,
        "related_queries",
    )


def converter_linha(linha: dict[str, str]) -> dict[str, Any]:
    """Converte uma linha do CSV aos tipos explícitos do schema BigQuery."""
    try:
        data = datetime.strptime(linha["data_coleta"], "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"data_coleta inválida: {linha['data_coleta']!r}") from exc

    try:
        posicao = int(linha["posicao"])
    except ValueError as exc:
        raise ValueError(f"posicao inválida: {linha['posicao']!r}") from exc

    valor_num = linha["valor_num"].strip()
    try:
        valor_num_convertido = float(valor_num) if valor_num else None
    except ValueError as exc:
        raise ValueError(f"valor_num inválido: {linha['valor_num']!r}") from exc

    saida: dict[str, Any] = {campo: linha[campo] for campo in CAMPOS_RELATED_QUERIES}
    saida["data_coleta"] = data.isoformat()
    saida["posicao"] = posicao
    saida["valor_num"] = valor_num_convertido
    saida["hora_ingestao"] = datetime.now(timezone.utc).isoformat()
    return saida


def job_id_lote(lote: LotePendente) -> str:
    return _job_id_lote(lote, "related_queries")

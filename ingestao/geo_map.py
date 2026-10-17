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
    "uf",
    "cod_tse",
    "recorte",
    "segmento",
    "porte",
    "rank_no_segmento_recorte",
)
_CAMPOS_SEGMENTACAO = (
    "uf",
    "cod_tse",
    "recorte",
    "segmento",
    "porte",
    "rank_no_segmento_recorte",
)
_CAMPOS_LEGADOS = CAMPOS_GEO_MAP[:-len(_CAMPOS_SEGMENTACAO)]


def _normalizar_hash_legado(linha: dict[str, str]) -> dict[str, str]:
    """Recria a representação antiga ao comparar checkpoints pré-migração."""
    antiga = {campo: linha.get(campo, "") for campo in _CAMPOS_LEGADOS}
    for campo in ("eh_ancora", "cidade_alvo"):
        antiga[campo] = {"true": "sim", "false": "não"}.get(antiga[campo].casefold(), antiga[campo])
    return antiga


def ler_lote_pendente(arquivo: Path, checkpoint: Path) -> LotePendente:
    """Lê somente registros GEO_MAP ainda não confirmados no BigQuery."""
    return ler_lote_csv(
        arquivo,
        checkpoint,
        CAMPOS_GEO_MAP,
        converter_linha,
        "geo_map",
        campos_opcionais=_CAMPOS_SEGMENTACAO,
        hash_compatibilidade=_normalizar_hash_legado,
    )


def converter_linha(linha: dict[str, str]) -> dict[str, Any]:
    """Converte uma linha do CSV aos tipos explícitos do schema BigQuery."""
    try:
        data = datetime.strptime(linha["data_coleta"], "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"data_coleta inválida: {linha['data_coleta']!r}") from exc

    ancora = linha["eh_ancora"].strip().casefold()
    booleanos = {"sim": True, "não": False, "nao": False, "true": True, "false": False}
    if ancora not in booleanos:
        raise ValueError(f"eh_ancora deve ser booleano, recebido: {linha['eh_ancora']!r}")

    saida: dict[str, Any] = {campo: linha.get(campo, "") for campo in CAMPOS_GEO_MAP}
    saida["data_coleta"] = data.isoformat()
    saida["eh_ancora"] = booleanos[ancora]
    alvo = linha["cidade_alvo"].strip().casefold()
    if alvo:
        if alvo not in booleanos:
            raise ValueError(f"cidade_alvo deve ser booleano ou vazio, recebido: {linha['cidade_alvo']!r}")
        saida["cidade_alvo"] = str(booleanos[alvo]).lower()
    else:
        saida["cidade_alvo"] = None
    for campo in ("cod_tse", "rank_no_segmento_recorte"):
        try:
            saida[campo] = int(saida[campo]) if saida[campo] else None
        except ValueError as exc:
            raise ValueError(f"{campo} inválido: {saida[campo]!r}") from exc
    for campo in ("valor", "indice_vs_ancora"):
        try:
            saida[campo] = float(linha[campo]) if linha[campo].strip() else None
        except ValueError as exc:
            raise ValueError(f"{campo} inválido: {linha[campo]!r}") from exc
    saida["hora_ingestao"] = datetime.now(timezone.utc).isoformat()
    return saida


def job_id_lote(lote: LotePendente) -> str:
    return _job_id_lote(lote, "geo_map")

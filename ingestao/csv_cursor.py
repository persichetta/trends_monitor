"""Leitura incremental com checkpoint, compartilhada pelas ingestões CSV."""
from __future__ import annotations

import csv
import hashlib
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class LotePendente:
    linhas: list[dict[str, Any]]
    total_linhas: int
    inicio: int
    geracao: str
    hash_prefixo: str


def _hash_linhas(linhas: list[dict[str, str]]) -> str:
    digest = hashlib.sha256()
    for linha in linhas:
        serializada = json.dumps(linha, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest.update(serializada.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _ler_checkpoint(caminho: Path) -> dict[str, Any] | None:
    if not caminho.exists():
        return None
    try:
        estado = json.loads(caminho.read_text(encoding="utf-8"))
        if not isinstance(estado.get("linhas_lidas"), int) or estado["linhas_lidas"] < 0:
            raise ValueError("linhas_lidas inválido")
        if not isinstance(estado.get("hash_prefixo"), str) or not isinstance(estado.get("geracao"), str):
            raise ValueError("hash_prefixo ou geracao inválido")
        return estado
    except (json.JSONDecodeError, OSError, ValueError, AttributeError) as exc:
        raise ValueError(f"Checkpoint inválido em {caminho}: {exc}") from exc


def ler_lote_csv(
    arquivo: Path,
    checkpoint: Path,
    campos_esperados: tuple[str, ...],
    converter: Callable[[dict[str, str]], dict[str, Any]],
    tipo: str,
    campos_opcionais: tuple[str, ...] = (),
    hash_compatibilidade: Callable[[dict[str, str]], dict[str, str]] | None = None,
) -> LotePendente:
    """Lê os registros não confirmados, detectando truncamento/reescrita do CSV."""
    if not arquivo.exists() or arquivo.stat().st_size == 0:
        return LotePendente([], 0, 0, uuid.uuid5(uuid.NAMESPACE_URL, tipo).hex, _hash_linhas([]))

    with arquivo.open("r", newline="", encoding="utf-8-sig") as f:
        leitor = csv.DictReader(f)
        campos = leitor.fieldnames
        if campos is None:
            raise ValueError(f"CSV sem cabeçalho: {arquivo}")
        faltantes_set = set(campos_esperados) - set(campos)
        extras_set = set(campos) - set(campos_esperados)
        if len(campos) != len(set(campos)) or not faltantes_set.issubset(campos_opcionais) or extras_set:
            faltantes = sorted(faltantes_set)
            extras = sorted(extras_set)
            raise ValueError(f"Cabeçalho inesperado em {arquivo}; faltantes={faltantes}, extras={extras}")

        registros: list[dict[str, str]] = []
        for numero, linha in enumerate(leitor, start=2):
            if None in linha or any(valor is None for valor in linha.values()):
                raise ValueError(f"Linha {numero} incompleta ou com colunas extras em {arquivo}")
            registros.append(linha)

    estado = _ler_checkpoint(checkpoint)
    inicio = 0
    geracao = uuid.uuid5(uuid.NAMESPACE_URL, f"{tipo}:{_hash_linhas(registros)}").hex
    if estado is not None:
        quantidade = estado["linhas_lidas"]
        prefixo = registros[:quantidade]
        hash_atual = _hash_linhas(prefixo) if quantidade <= len(registros) else ""
        hash_legado = (
            _hash_linhas([hash_compatibilidade(linha) for linha in prefixo])
            if hash_compatibilidade and quantidade <= len(registros)
            else ""
        )
        if quantidade <= len(registros) and estado["hash_prefixo"] in {hash_atual, hash_legado}:
            inicio = quantidade
            geracao = estado["geracao"]
        else:
            geracao = uuid.uuid5(uuid.NAMESPACE_URL, f"{tipo}:{_hash_linhas(registros)}").hex

    return LotePendente(
        [converter(linha) for linha in registros[inicio:]],
        len(registros),
        inicio,
        geracao,
        _hash_linhas(registros),
    )


def job_id_lote(lote: LotePendente, tipo: str) -> str:
    """Gera ID estável para que um retry recupere o mesmo load job."""
    conteudo = json.dumps(
        [{k: v for k, v in linha.items() if k != "hora_ingestao"} for linha in lote.linhas],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(conteudo.encode("utf-8")).hexdigest()[:16]
    return f"{tipo}_{lote.geracao[:12]}_{lote.inicio}_{lote.total_linhas}_{digest}"


def salvar_checkpoint(caminho: Path, lote: LotePendente) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    estado = {
        "linhas_lidas": lote.total_linhas,
        "hash_prefixo": lote.hash_prefixo,
        "geracao": lote.geracao,
    }
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    temporario.write_text(json.dumps(estado, indent=2), encoding="utf-8")
    temporario.replace(caminho)

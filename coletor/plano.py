"""Transforma os arquivos de config/ na lista de buscas do dia."""
from __future__ import annotations

import csv
import datetime as dt
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

RAIZ = Path(__file__).resolve().parent.parent
LIMITE_TERMOS = {"TIMESERIES": 5, "GEO_MAP": 5, "GEO_MAP_0": 1, "RELATED_QUERIES": 1, "RELATED_TOPICS": 1}


def normalizar(s: str) -> str:
    """Sem acento e minúsculo. Mesma regra da função norm() sugerida para o BigQuery."""
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn").lower().strip()


@dataclass
class Busca:
    job: str
    tipo: str
    termos: list[str]
    params: dict[str, Any]
    grupo: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def id(self) -> str:
        """Identificador estável, usado para não repetir a mesma busca no mesmo dia."""
        partes = [self.job]
        if self.meta.get("multi_geo"):
            partes.append(self.params["geo"])
        partes.append(self.grupo or self.termos[0])
        return ":".join(partes)


def carregar_config(pasta: Path | None = None) -> tuple[dict, dict]:
    pasta = pasta or RAIZ / "config"
    termos = yaml.safe_load((pasta / "termos.yaml").read_text(encoding="utf-8"))
    coletas = yaml.safe_load((pasta / "coletas.yaml").read_text(encoding="utf-8"))
    validar(termos, coletas)
    return termos, coletas


def carregar_segmentacao(coletas: dict) -> dict[tuple[str, str], dict]:
    """Lê a lista de cidades da segmentação. Chave: (UF, nome normalizado)."""
    caminho = coletas.get("segmentacao")
    if not caminho:
        return {}
    caminho = Path(caminho)
    if not caminho.is_absolute():
        caminho = RAIZ / caminho
    with caminho.open(encoding="utf-8") as f:
        return {(r["uf"], normalizar(r["municipio"])): r for r in csv.DictReader(f)}


def validar(termos: dict, coletas: dict) -> None:
    ancora = termos["ancora"]
    for nome, lista in termos["grupos"].items():
        if ancora in lista:
            raise ValueError(f"Grupo {nome}: não repita a âncora, ela é adicionada sozinha.")
        if len(lista) + 1 > 5:
            raise ValueError(f"Grupo {nome}: máximo de 4 termos + âncora.")
        for t in lista:
            if t not in termos["macrotemas"]:
                raise ValueError(f"Termo '{t}' sem macrotema em termos.yaml.")
    for job in coletas["jobs"]:
        for g in job.get("grupos", []):
            if g not in termos["grupos"]:
                raise ValueError(f"Job {job['nome']}: grupo '{g}' não existe.")
        if "geo" in job and "geos" in job:
            raise ValueError(f"Job {job['nome']}: use 'geo' ou 'geos', não os dois.")


def _termos_do_job(job: dict, termos: dict) -> list[str]:
    escolha = job.get("termos")
    if escolha == "candidatos":
        return list(termos["candidatos"])
    if escolha == "temas":
        return [t for t in termos["macrotemas"] if t not in termos["candidatos"]]
    return list(escolha or [])


def buscas_do_dia(data: dt.date, termos: dict, coletas: dict) -> list[Busca]:
    ini = dt.date.fromisoformat(coletas["periodo"]["inicio"])
    fim = dt.date.fromisoformat(coletas["periodo"]["fim"])
    if not (ini <= data <= fim):
        return []
    padrao = coletas.get("parametros_padrao", {})
    saida: list[Busca] = []
    for job in coletas["jobs"]:
        freq = int(job.get("frequencia_dias", 1))
        desloc = int(job.get("deslocamento", 0))
        if (data - ini).days - desloc < 0 or ((data - ini).days - desloc) % freq != 0:
            continue
        geos = job.get("geos") or [job.get("geo", "BR")]
        meta = {"cidades_alvo": job.get("cidades_alvo", []), "multi_geo": "geos" in job}
        for geo in geos:
            base = {**padrao, "data_type": job["tipo"], "geo": geo}
            for k in ("date", "region", "cat", "gprop"):
                if k in job:
                    base[k] = job[k]
            if job.get("include_low_search_volume"):
                base["include_low_search_volume"] = "true"

            if job["tipo"] in ("GEO_MAP", "TIMESERIES"):
                for g in job["grupos"]:
                    lista = termos["grupos"][g] + [termos["ancora"]]
                    saida.append(Busca(job["nome"], job["tipo"], lista, {**base, "q": ",".join(lista)}, grupo=g, meta=meta))
            else:
                for t in _termos_do_job(job, termos):
                    saida.append(Busca(job["nome"], job["tipo"], [t], {**base, "q": t}, meta=meta))

    for b in saida:
        if len(b.termos) > LIMITE_TERMOS[b.tipo]:
            raise ValueError(f"{b.id}: {len(b.termos)} termos, limite {LIMITE_TERMOS[b.tipo]}.")
    return saida

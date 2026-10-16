"""Transforma os arquivos de config/ na lista de buscas do dia."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

RAIZ = Path(__file__).resolve().parent.parent
LIMITE_TERMOS = {"TIMESERIES": 5, "GEO_MAP": 5, "GEO_MAP_0": 1, "RELATED_QUERIES": 1, "RELATED_TOPICS": 1}


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
        return f"{self.job}:{self.grupo or self.termos[0]}"


def carregar_config(pasta: Path | None = None) -> tuple[dict, dict]:
    pasta = pasta or RAIZ / "config"
    termos = yaml.safe_load((pasta / "termos.yaml").read_text(encoding="utf-8"))
    coletas = yaml.safe_load((pasta / "coletas.yaml").read_text(encoding="utf-8"))
    validar(termos, coletas)
    return termos, coletas


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


def _termos_do_job(job: dict, termos: dict) -> list[str]:
    escolha = job.get("termos")
    if escolha == "candidatos":
        return list(termos["candidatos"])
    if escolha == "temas":
        return [t for t, m in termos["macrotemas"].items() if t not in termos["candidatos"]]
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
        if (data - ini).days % freq != 0:
            continue
        base = {**padrao, "data_type": job["tipo"], "geo": job.get("geo", "BR")}
        for k in ("date", "region", "cat", "gprop"):
            if k in job:
                base[k] = job[k]
        if job.get("include_low_search_volume"):
            base["include_low_search_volume"] = "true"
        meta = {"cidades_alvo": job.get("cidades_alvo", [])}

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

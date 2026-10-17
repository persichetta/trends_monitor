"""Gravação em disco: JSON bruto (auditoria) + CSVs acumulados + log de coletas."""
from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path

from .plano import RAIZ

DADOS = Path(os.environ.get("COLETOR_DADOS", RAIZ / "data"))
LOG = DADOS / "log_coletas.csv"
CAMPOS_LOG = ["data_coleta", "horario_utc", "busca_id", "tipo", "status", "linhas", "search_id", "mensagem"]


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def salvar_bruto(resp: dict, data_coleta: str, busca_id: str) -> Path:
    pasta = DADOS / "bruto" / data_coleta
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / f"{_slug(busca_id)}.json"
    # remove qualquer eco da chave por segurança
    resp = dict(resp)
    resp["search_parameters"] = {k: v for k, v in resp.get("search_parameters", {}).items() if k != "api_key"}
    caminho.write_text(json.dumps(resp, ensure_ascii=False, indent=1), encoding="utf-8")
    return caminho


_SIM_NAO = {"sim": "true", "não": "false", "nao": "false"}


def _migrar(caminho: Path, campos_novos: list[str]) -> list[str]:
    """Reescreve um CSV antigo com as colunas novas (vazias) e sim/não -> true/false."""
    with caminho.open(encoding="utf-8") as f:
        leitor = csv.DictReader(f)
        antigos = list(leitor.fieldnames or [])
        linhas = list(leitor)
    campos = antigos + [c for c in campos_novos if c not in antigos]
    for r in linhas:
        for c in ("eh_ancora", "cidade_alvo"):
            if c in r:
                r[c] = _SIM_NAO.get(r[c], r[c])
    with caminho.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        w.writerows(linhas)
    return campos


def anexar_csv(nome: str, linhas: list[dict]) -> None:
    if not linhas:
        return
    DADOS.mkdir(parents=True, exist_ok=True)
    caminho = DADOS / nome
    novo = not caminho.exists()
    campos = list(linhas[0].keys())
    if not novo:
        with caminho.open(encoding="utf-8") as f:
            existentes = next(csv.reader(f))
        precisa_migrar = any(c not in existentes for c in campos)
        if not precisa_migrar and ("eh_ancora" in existentes or "cidade_alvo" in existentes):
            with caminho.open(encoding="utf-8") as f:
                precisa_migrar = any(r.get("eh_ancora") in _SIM_NAO or r.get("cidade_alvo") in _SIM_NAO
                                     for r in csv.DictReader(f))
        campos = _migrar(caminho, campos) if precisa_migrar else existentes
    with caminho.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        if novo:
            w.writeheader()
        w.writerows(linhas)


def registrar(registro: dict) -> None:
    DADOS.mkdir(parents=True, exist_ok=True)
    novo = not LOG.exists()
    with LOG.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_LOG, extrasaction="ignore")
        if novo:
            w.writeheader()
        w.writerow(registro)


def ja_coletadas(data_coleta: str) -> set[str]:
    """Buscas já concluídas na data (evita gastar cota se o job rodar duas vezes)."""
    if not LOG.exists():
        return set()
    with LOG.open(encoding="utf-8") as f:
        return {r["busca_id"] for r in csv.DictReader(f)
                if r["data_coleta"] == data_coleta and r["status"] in ("ok", "sem_resultados")}

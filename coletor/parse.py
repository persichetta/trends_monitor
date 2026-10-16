"""Converte as respostas da SerpApi em linhas de tabela (formato longo)."""
from __future__ import annotations

import unicodedata
from typing import Any

from .plano import Busca


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().strip()


def _num(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def geo_map(resp: dict, busca: Busca, data_coleta: str, termos_cfg: dict) -> list[dict]:
    """GEO_MAP: uma linha por (local, termo). Aceita resposta com 1 ou vários termos."""
    ancora = termos_cfg["ancora"]
    macro = termos_cfg["macrotemas"]
    alvo = {_norm(c) for c in busca.meta.get("cidades_alvo", [])}
    linhas: list[dict] = []

    itens = resp.get("compared_breakdown_by_region")
    if itens is None:  # resposta de termo único
        itens = [
            {**i, "values": [{"query": busca.termos[0], "extracted_value": i.get("extracted_value")}]}
            for i in resp.get("interest_by_region", [])
        ]

    for item in itens:
        valores = {v.get("query"): _num(v.get("extracted_value")) for v in item.get("values", [])}
        v_ancora = valores.get(ancora)
        for termo, valor in valores.items():
            indice = round(valor / v_ancora * 100, 1) if (valor is not None and v_ancora) else None
            linhas.append({
                "data_coleta": data_coleta,
                "job": busca.job,
                "grupo": busca.grupo,
                "geo_busca": busca.params.get("geo"),
                "resolucao": busca.params.get("region"),
                "periodo": busca.params.get("date"),
                "local": item.get("location"),
                "local_codigo": item.get("geo"),
                "cidade_alvo": "sim" if alvo and _norm(item.get("location", "")) in alvo else ("não" if alvo else ""),
                "termo": termo,
                "macrotema": macro.get(termo, ""),
                "eh_ancora": "sim" if termo == ancora else "não",
                "valor": valor,
                "indice_vs_ancora": indice,
            })
    return linhas


def related_queries(resp: dict, busca: Busca, data_coleta: str, termos_cfg: dict) -> list[dict]:
    """RELATED_QUERIES: uma linha por consulta relacionada (top e em alta)."""
    rq = resp.get("related_queries") or {}
    termo = busca.termos[0]
    linhas: list[dict] = []
    for lista in ("rising", "top"):
        for pos, item in enumerate(rq.get(lista, []) or [], 1):
            linhas.append({
                "data_coleta": data_coleta,
                "job": busca.job,
                "geo_busca": busca.params.get("geo"),
                "periodo": busca.params.get("date"),
                "termo_base": termo,
                "macrotema": termos_cfg["macrotemas"].get(termo, ""),
                "lista": "em alta" if lista == "rising" else "top",
                "posicao": pos,
                "consulta": item.get("query"),
                "valor": item.get("value"),          # ex.: "Breakout", "+250%", "100"
                "valor_num": _num(item.get("extracted_value")),
            })
    return linhas


def timeseries(resp: dict, busca: Busca, data_coleta: str, termos_cfg: dict) -> list[dict]:
    """TIMESERIES: uma linha por (instante, termo). Não usado no plano padrão."""
    linhas: list[dict] = []
    for ponto in (resp.get("interest_over_time") or {}).get("timeline_data", []):
        for v in ponto.get("values", []):
            linhas.append({
                "data_coleta": data_coleta,
                "job": busca.job,
                "grupo": busca.grupo,
                "geo_busca": busca.params.get("geo"),
                "periodo": busca.params.get("date"),
                "instante": ponto.get("date"),
                "timestamp": ponto.get("timestamp"),
                "termo": v.get("query"),
                "macrotema": termos_cfg["macrotemas"].get(v.get("query"), ""),
                "valor": _num(v.get("extracted_value")),
            })
    return linhas


PARSERS = {"GEO_MAP": geo_map, "GEO_MAP_0": geo_map, "RELATED_QUERIES": related_queries, "TIMESERIES": timeseries}
ARQUIVOS = {"GEO_MAP": "geo_map.csv", "GEO_MAP_0": "geo_map.csv", "RELATED_QUERIES": "related_queries.csv", "TIMESERIES": "timeseries.csv"}

"""CLI para ingerir GEO_MAP e related_queries sem repetir linhas carregadas.

Uso: python -m ingestao {executar,geo-map,related-queries}
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

from .config import RAIZ
from .rotina import executar_coleta_e_ingestao
from .servico import executar_geo_map, executar_related_queries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ingestao", description="Ingestão manual de dados no BigQuery")
    sub = parser.add_subparsers(dest="comando", required=True)
    geo = sub.add_parser("geo-map", help="ingere linhas novas de data/geo_map.csv")
    geo.add_argument("--arquivo", type=Path, default=RAIZ / "data" / "geo_map.csv")
    geo.add_argument(
        "--checkpoint",
        type=Path,
        default=RAIZ / "data" / "ingestao" / "geo_map_checkpoint.json",
    )
    related = sub.add_parser(
        "related-queries",
        help="ingere linhas novas de data/related_queries.csv",
    )
    related.add_argument("--arquivo", type=Path, default=RAIZ / "data" / "related_queries.csv")
    related.add_argument(
        "--checkpoint",
        type=Path,
        default=RAIZ / "data" / "ingestao" / "related_queries_checkpoint.json",
    )
    rotina = sub.add_parser("executar", help="executa o coletor e ingere GEO_MAP e related queries")
    rotina.add_argument("--data", help="data da coleta no formato AAAA-MM-DD; padrão: hoje")
    rotina.add_argument("--somente", help="executa apenas um job do coletor")
    rotina.add_argument("--forcar", action="store_true", help="refaz buscas já concluídas nessa data")
    args = parser.parse_args(argv)

    try:
        if args.comando == "geo-map":
            return executar_geo_map(args.arquivo, args.checkpoint)
        if args.comando == "related-queries":
            return executar_related_queries(args.arquivo, args.checkpoint)
        if args.comando == "executar":
            data = dt.date.fromisoformat(args.data) if args.data else None
            return executar_coleta_e_ingestao(data, args.somente, args.forcar)
    except Exception as exc:
        print(f"Falha na ingestão: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

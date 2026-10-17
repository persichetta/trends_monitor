"""Orquestra uma execução do coletor seguida das ingestões GEO_MAP e related queries."""
from __future__ import annotations

from datetime import date
import sys

from coletor.__main__ import main as executar_cli_coletor

from .config import RAIZ
from .servico import executar_geo_map, executar_related_queries


def executar_coleta_e_ingestao(
    data: date | None = None,
    somente: str | None = None,
    forcar: bool = False,
) -> int:
    """Executa primeiro o coletor; depois ingere o CSV incrementalmente.

    Mesmo se o coletor retornar um status de falha parcial, a ingestão tenta
    carregar as linhas que ele conseguiu gravar antes da falha.
    """
    argumentos = ["executar"]
    if data:
        argumentos.extend(("--data", data.isoformat()))
    if somente:
        argumentos.extend(("--somente", somente))
    if forcar:
        argumentos.append("--forcar")

    status_coleta = executar_cli_coletor(argumentos)
    status_ingestao = 0
    for ingerir in (executar_geo_map, executar_related_queries):
        try:
            status_ingestao = ingerir() or status_ingestao
        except Exception as exc:
            print(f"Falha na ingestão {ingerir.__name__}: {exc}", file=sys.stderr)
            status_ingestao = 1
    return status_coleta or status_ingestao

"""Linha de comando.

    python -m coletor cota                 # buscas restantes (não gasta cota)
    python -m coletor plano [--data D]     # mostra o que seria coletado (não gasta cota)
    python -m coletor teste [--n 5]        # roda só as N primeiras buscas do dia
    python -m coletor executar [--data D] [--somente JOB] [--forcar]
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import time
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from . import armazenamento as arm
from .cliente import ClienteSerpApi, ErroAutenticacao, ErroCota, ErroSerpApi, SemResultados
from .parse import ARQUIVOS, PARSERS
from .plano import buscas_do_dia, carregar_config, carregar_segmentacao

FUSO = ZoneInfo("America/Sao_Paulo")


def _hoje() -> dt.date:
    return dt.datetime.now(FUSO).date()


def _cliente() -> ClienteSerpApi:
    load_dotenv()
    return ClienteSerpApi(os.environ.get("SERPAPI_KEY", ""))


def cmd_cota(_args) -> int:
    c = _cliente().conta()
    print(f"Plano: {c.get('plan_name')} | renovação: {c.get('plan_renewal_date')}")
    print(f"Buscas restantes: {c.get('total_searches_left')} de {c.get('searches_per_month')}")
    print(f"Usadas no mês: {c.get('this_month_usage')} | nesta hora: {c.get('this_hour_searches')}"
          f" (limite {c.get('account_rate_limit_per_hour')}/h)")
    return 0


def cmd_plano(args) -> int:
    termos, coletas = carregar_config()
    data = dt.date.fromisoformat(args.data) if args.data else _hoje()
    buscas = buscas_do_dia(data, termos, coletas)
    if args.somente:
        buscas = [b for b in buscas if b.job == args.somente]
    print(f"{data}: {len(buscas)} buscas")
    for b in buscas:
        print(f"  {b.id:<44} {b.tipo:<16} geo={b.params['geo']:<6} q={b.params['q']}")
    fim = dt.date.fromisoformat(coletas["periodo"]["fim"])
    if data <= fim:
        total = sum(len(buscas_do_dia(data + dt.timedelta(d), termos, coletas)) for d in range((fim - data).days + 1))
        print(f"Total previsto de {data} a {fim}: {total} buscas")
    return 0


def executar(data: dt.date, somente: str | None = None, limite: int | None = None, forcar: bool = False) -> int:
    termos, coletas = carregar_config()
    orc = coletas["orcamento"]
    segmentacao = carregar_segmentacao(coletas)
    buscas = buscas_do_dia(data, termos, coletas)
    if somente:
        buscas = [b for b in buscas if b.job == somente]
    data_s = data.isoformat()
    if not forcar:
        feitas = arm.ja_coletadas(data_s)
        buscas = [b for b in buscas if b.id not in feitas]
    if limite:
        buscas = buscas[:limite]
    if not buscas:
        print(f"{data_s}: nada a coletar.")
        return 0

    cli = _cliente()
    conta = cli.conta()
    restantes = int(conta.get("total_searches_left") or 0)
    nesta_hora = int(conta.get("this_hour_searches") or 0)
    lim_hora = min(int(conta.get("account_rate_limit_per_hour") or orc["limite_por_hora"]), orc["limite_por_hora"])
    print(f"Cota: {restantes} restantes, {nesta_hora} nesta hora. Planejadas: {len(buscas)}.")

    falhas = 0
    for i, b in enumerate(buscas):
        if restantes - 1 < orc["reserva_minima"]:
            print(f"Parando: a reserva mínima ({orc['reserva_minima']}) seria atingida.")
            break
        if nesta_hora + 1 > lim_hora:
            print("Parando: limite por hora atingido. Rode de novo na próxima hora.")
            break
        reg = {"data_coleta": data_s, "horario_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
               "busca_id": b.id, "tipo": b.tipo}
        try:
            resp = cli.trends(b.params)
            arm.salvar_bruto(resp, data_s, b.id)
            linhas = PARSERS[b.tipo](resp, b, data_s, termos, segmentacao=segmentacao)
            arm.anexar_csv(ARQUIVOS[b.tipo], linhas)
            reg.update(status="ok", linhas=len(linhas),
                       search_id=(resp.get("search_metadata") or {}).get("id", ""))
            print(f"  ok  {b.id} ({len(linhas)} linhas)")
        except SemResultados as e:
            reg.update(status="sem_resultados", linhas=0, mensagem=str(e)[:200])
            print(f"  --  {b.id}: sem dados no Trends")
        except (ErroAutenticacao, ErroCota) as e:
            reg.update(status="erro_fatal", mensagem=str(e)[:200])
            arm.registrar(reg)
            print(f"  !!  {b.id}: {e}")
            return 2
        except ErroSerpApi as e:
            falhas += 1
            reg.update(status="erro", mensagem=str(e)[:200])
            print(f"  !!  {b.id}: {e}")
        arm.registrar(reg)
        restantes -= 1
        nesta_hora += 1
        if i < len(buscas) - 1:
            time.sleep(orc["pausa_entre_buscas_s"])
    return 1 if falhas else 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="coletor", description="Coleta de Google Trends via SerpApi")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("cota", help="mostra buscas restantes (não gasta cota)")
    sp = sub.add_parser("plano", help="lista as buscas do dia sem executar")
    sp.add_argument("--data"); sp.add_argument("--somente")
    st = sub.add_parser("teste", help="executa só as N primeiras buscas do dia")
    st.add_argument("--n", type=int, default=5)
    se = sub.add_parser("executar", help="executa a coleta do dia")
    se.add_argument("--data"); se.add_argument("--somente"); se.add_argument("--forcar", action="store_true")
    a = p.parse_args(argv)
    try:
        if a.cmd == "cota":
            return cmd_cota(a)
        if a.cmd == "plano":
            return cmd_plano(a)
        if a.cmd == "teste":
            return executar(_hoje(), limite=a.n)
        return executar(dt.date.fromisoformat(a.data) if a.data else _hoje(), a.somente, forcar=a.forcar)
    except ErroAutenticacao as e:
        print(f"Erro de autenticação: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

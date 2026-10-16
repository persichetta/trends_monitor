import datetime as dt
import json
import os
from pathlib import Path

import pytest

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def pasta_dados(tmp_path, monkeypatch):
    monkeypatch.setenv("COLETOR_DADOS", str(tmp_path))
    import importlib
    import coletor.armazenamento as arm
    importlib.reload(arm)
    import coletor.__main__ as m
    importlib.reload(m)
    yield tmp_path


def test_plano_respeita_orcamento():
    from coletor.plano import buscas_do_dia, carregar_config
    termos, coletas = carregar_config()
    d0 = dt.date(2026, 10, 16)
    assert len(buscas_do_dia(d0, termos, coletas)) == 5 + 5 + 3 + 14
    assert len(buscas_do_dia(d0 + dt.timedelta(1), termos, coletas)) == 13
    total = sum(len(buscas_do_dia(d0 + dt.timedelta(i), termos, coletas)) for i in range(9))
    assert total == 159          # + 5 de teste = 164, dentro das 250 com reserva
    assert buscas_do_dia(dt.date(2026, 10, 25), termos, coletas) == []


def test_grupos_tem_ancora_e_no_maximo_5():
    from coletor.plano import buscas_do_dia, carregar_config
    termos, coletas = carregar_config()
    for b in buscas_do_dia(dt.date(2026, 10, 16), termos, coletas):
        if b.tipo == "GEO_MAP":
            assert termos["ancora"] in b.termos and len(b.termos) <= 5
        else:
            assert len(b.termos) == 1


def test_parse_geo_map_indice_ancora():
    from coletor.parse import geo_map
    from coletor.plano import buscas_do_dia, carregar_config
    termos, coletas = carregar_config()
    b = [x for x in buscas_do_dia(dt.date(2026, 10, 16), termos, coletas) if x.id == "cidades_sp:G1"][0]
    linhas = geo_map(json.loads((FIX / "geo_map.json").read_text()), b, "2026-10-16", termos)
    assert len(linhas) == 10
    camp_inss = [l for l in linhas if l["local"] == "Campinas" and l["termo"] == "inss"][0]
    assert camp_inss["indice_vs_ancora"] == 75.0 and camp_inss["cidade_alvo"] == "sim"
    assert camp_inss["macrotema"] == "Aposentadoria e renda"
    gru = [l for l in linhas if l["local"] == "Guarulhos"][0]
    assert gru["cidade_alvo"] == "não"


def test_parse_related():
    from coletor.parse import related_queries
    from coletor.plano import Busca, carregar_config
    termos, _ = carregar_config()
    b = Busca("relacionadas_candidatos", "RELATED_QUERIES", ["flávio bolsonaro"], {"geo": "BR", "q": "flávio bolsonaro"})
    linhas = related_queries(json.loads((FIX / "related.json").read_text()), b, "2026-10-16", termos)
    assert [l["lista"] for l in linhas] == ["em alta", "em alta", "top"]
    assert linhas[0]["valor"] == "Breakout" and linhas[1]["valor_num"] == 250


class ClienteFalso:
    def __init__(self, *a, **k):
        self.chamadas = 0
    def conta(self):
        return {"total_searches_left": 200, "this_hour_searches": 0, "account_rate_limit_per_hour": 50}
    def trends(self, params):
        self.chamadas += 1
        if params["data_type"] == "RELATED_QUERIES":
            return json.loads((FIX / "related.json").read_text())
        return json.loads((FIX / "geo_map.json").read_text())


def test_executar_idempotente_e_sem_chave(monkeypatch, pasta_dados):
    import coletor.__main__ as m
    falso = ClienteFalso()
    monkeypatch.setattr(m, "_cliente", lambda: falso)
    monkeypatch.setattr(m.time, "sleep", lambda s: None)
    d = dt.date(2026, 10, 17)
    assert m.executar(d) == 0
    assert falso.chamadas == 13
    assert m.executar(d) == 0          # segunda vez: nada a coletar
    assert falso.chamadas == 13
    brutos = list((pasta_dados / "bruto" / "2026-10-17").glob("*.json"))
    assert brutos and all("NAO-DEVE-APARECER" not in p.read_text() for p in brutos)
    assert (pasta_dados / "geo_map.csv").exists() and (pasta_dados / "related_queries.csv").exists()


def test_reserva_minima_interrompe(monkeypatch):
    import coletor.__main__ as m
    falso = ClienteFalso()
    falso.conta = lambda: {"total_searches_left": 33, "this_hour_searches": 0, "account_rate_limit_per_hour": 50}
    monkeypatch.setattr(m, "_cliente", lambda: falso)
    monkeypatch.setattr(m.time, "sleep", lambda s: None)
    m.executar(dt.date(2026, 10, 17))
    assert falso.chamadas == 3          # 33 restantes, reserva 30

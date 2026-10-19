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
    assert len(buscas_do_dia(d0, termos, coletas)) == 11 + 55 + 3 + 33
    assert len(buscas_do_dia(d0 + dt.timedelta(1), termos, coletas)) == 69
    total = sum(len(buscas_do_dia(d0 + dt.timedelta(i), termos, coletas)) for i in range(9))
    assert total == 720          # 9 dias x 69 + 3 coletas de temas x 33
    assert max(len(buscas_do_dia(d0 + dt.timedelta(i), termos, coletas)) for i in range(9)) == 102
    assert buscas_do_dia(dt.date(2026, 10, 25), termos, coletas) == []


def test_grupos_tem_ancora_e_no_maximo_5():
    from coletor.plano import buscas_do_dia, carregar_config
    termos, coletas = carregar_config()
    for b in buscas_do_dia(dt.date(2026, 10, 16), termos, coletas):
        if b.tipo == "GEO_MAP":
            assert termos["ancora"] in b.termos and len(b.termos) <= 5
        else:
            assert len(b.termos) == 1


def test_config_tem_apenas_os_termos_definidos():
    from coletor.plano import buscas_do_dia, carregar_config
    termos, coletas = carregar_config()
    temas = {
        "sus", "upa", "ubs", "posto de saúde", "quem criou o sus",
        "prouni", "quem criou prouni", "fundeb", "escola pública",
        "bpc loas", "cadúnico", "aposentadoria 70 anos", "inss",
        "roberta luchsinger", "luchsinger", "lulinha", "filho do lula",
        "filho lula bateu", "lula lobista", "lula socio", "lula vorcaro",
        "134 milhoes", "flavio vorcaro", "inimigo do trabalhador",
        "privatizar o sus", "lottenberg", "flavio 6x1", "flavio miliciano",
        "flavio ana clara", "flavio comando vermelho", "bolsonaro miliciano",
        "armas bolsonaro", "inflacao bolsonaro",
    }
    candidatos = {"lula", "bolsonaro", "flavio bolsonaro"}
    assert set(termos["macrotemas"]) == temas | candidatos
    assert set(termos["candidatos"]) == candidatos
    buscas = buscas_do_dia(dt.date(2026, 10, 16), termos, coletas)
    relacionadas_temas = {b.termos[0] for b in buscas if b.job == "relacionadas_temas"}
    assert relacionadas_temas == temas
    cand = next(b for b in buscas if b.grupo == "CAND")
    assert cand.termos.count(termos["ancora"]) == 1


def test_parse_geo_map_indice_ancora():
    from coletor.parse import geo_map
    from coletor.plano import buscas_do_dia, carregar_config
    termos, coletas = carregar_config()
    from coletor.plano import carregar_segmentacao
    seg = carregar_segmentacao(coletas)
    assert len(seg) == 1794
    b = [x for x in buscas_do_dia(dt.date(2026, 10, 16), termos, coletas) if x.id == "cidades:BR-SP:G4"][0]
    linhas = geo_map(json.loads((FIX / "geo_map.json").read_text()), b, "2026-10-16", termos, segmentacao=seg)
    assert len(linhas) == 4
    camp_inss = [l for l in linhas if l["local"] == "Campinas" and l["termo"] == "inss"][0]
    assert camp_inss["indice_vs_ancora"] == 75.0 and camp_inss["cidade_alvo"] == "true"
    assert camp_inss["macrotema"] == "Aposentadoria" and camp_inss["segmento"] == ""   # alvo, fora da segmentação
    gru = [l for l in linhas if l["local"] == "Guarulhos"][0]
    assert gru["cidade_alvo"] == "true" and gru["recorte"] == "RM São Paulo" and gru["uf"] == "SP"
    assert gru["segmento"].startswith("3.") and gru["cod_tse"]
    assert {l["eh_ancora"] for l in linhas} == {"true", "false"}


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
    assert falso.chamadas == 50
    assert m.executar(d) == 0          # retoma buscas pendentes após o limite horário
    assert falso.chamadas == 69
    brutos = list((pasta_dados / "bruto" / "2026-10-17").glob("*.json"))
    assert brutos and all("NAO-DEVE-APARECER" not in p.read_text() for p in brutos)
    assert (pasta_dados / "geo_map.csv").exists() and (pasta_dados / "related_queries.csv").exists()


def test_csv_zerado_recebe_cabecalho_ao_primeiro_append(pasta_dados):
    import csv
    from coletor import armazenamento as arm

    (pasta_dados / "geo_map.csv").write_text("", encoding="utf-8")
    arm.anexar_csv("geo_map.csv", [{"data_coleta": "2026-10-16", "termo": "inss"}])
    with (pasta_dados / "geo_map.csv").open(encoding="utf-8") as f:
        assert next(csv.reader(f)) == ["data_coleta", "termo"]

    arm.LOG.write_text("", encoding="utf-8")
    arm.registrar({"data_coleta": "2026-10-16", "status": "ok"})
    with arm.LOG.open(encoding="utf-8") as f:
        assert next(csv.reader(f)) == arm.CAMPOS_LOG


def test_reserva_minima_interrompe(monkeypatch):
    import coletor.__main__ as m
    falso = ClienteFalso()
    falso.conta = lambda: {"total_searches_left": 33, "this_hour_searches": 0, "account_rate_limit_per_hour": 50}
    monkeypatch.setattr(m, "_cliente", lambda: falso)
    monkeypatch.setattr(m.time, "sleep", lambda s: None)
    m.executar(dt.date(2026, 10, 17))
    assert falso.chamadas == 3          # 33 restantes, reserva 30


def test_migra_csv_antigo(pasta_dados):
    import csv
    import coletor.armazenamento as arm
    antigo = pasta_dados / "geo_map.csv"
    antigo.write_text("data_coleta,termo,eh_ancora,cidade_alvo,valor\n2026-10-16,inss,não,sim,30\n", encoding="utf-8")
    arm.anexar_csv("geo_map.csv", [{"data_coleta": "2026-10-17", "termo": "inss", "eh_ancora": "false",
                                    "cidade_alvo": "true", "valor": 31, "segmento": "2. Disputa voto a voto"}])
    rows = list(csv.DictReader(antigo.open(encoding="utf-8")))
    assert rows[0]["eh_ancora"] == "false" and rows[0]["cidade_alvo"] == "true" and rows[0]["segmento"] == ""
    assert rows[1]["segmento"] == "2. Disputa voto a voto"

import csv
import json
from pathlib import Path

import pytest

from ingestao.geo_map import (
    CAMPOS_GEO_MAP,
    converter_linha,
    job_id_lote,
    ler_lote_pendente,
    salvar_checkpoint,
)
from ingestao.related_queries import (
    CAMPOS_RELATED_QUERIES,
    converter_linha as converter_related,
    ler_lote_pendente as ler_related_pendente,
)


def _linha(**alteracoes):
    linha = {
        "data_coleta": "2026-10-16",
        "job": "cidades_sp",
        "grupo": "G1",
        "geo_busca": "BR-SP",
        "resolucao": "CITY",
        "periodo": "now 7-d",
        "local": "Campinas",
        "local_codigo": "",
        "cidade_alvo": "sim",
        "termo": "inss",
        "macrotema": "Aposentadoria e renda",
        "eh_ancora": "não",
        "valor": "30.0",
        "indice_vs_ancora": "75.0",
    }
    linha.update(alteracoes)
    return linha


def _escrever_csv(caminho: Path, linhas):
    with caminho.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CAMPOS_GEO_MAP)
        writer.writeheader()
        writer.writerows(linhas)


def _linha_related(**alteracoes):
    linha = {
        "data_coleta": "2026-10-16",
        "job": "relacionadas_candidatos",
        "geo_busca": "BR",
        "periodo": "now 1-d",
        "termo_base": "lula",
        "macrotema": "Candidatos",
        "lista": "em alta",
        "posicao": "1",
        "consulta": "como foi a entrevista do lula na globo",
        "valor": "Aumento repentino",
        "valor_num": "166800.0",
    }
    linha.update(alteracoes)
    return linha


def _escrever_related_csv(caminho: Path, linhas):
    with caminho.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CAMPOS_RELATED_QUERIES)
        writer.writeheader()
        writer.writerows(linhas)


def test_converter_linha_aplica_tipos_bigquery():
    linha = converter_linha(_linha())
    assert linha["data_coleta"] == "2026-10-16"
    assert linha["eh_ancora"] is False
    assert linha["valor"] == 30.0
    assert linha["indice_vs_ancora"] == 75.0
    assert linha["hora_ingestao"].endswith("+00:00")


def test_conversor_aceita_valores_numericos_vazios():
    linha = converter_linha(_linha(valor="", indice_vs_ancora="", eh_ancora="sim"))
    assert linha["valor"] is None
    assert linha["indice_vs_ancora"] is None
    assert linha["eh_ancora"] is True


@pytest.mark.parametrize(
    ("alteracoes", "mensagem"),
    [
        ({"data_coleta": "16/10/2026"}, "data_coleta inválida"),
        ({"eh_ancora": "talvez"}, "eh_ancora"),
        ({"valor": "muitos"}, "valor inválido"),
    ],
)
def test_converter_rejeita_dados_invalidos(alteracoes, mensagem):
    with pytest.raises(ValueError, match=mensagem):
        converter_linha(_linha(**alteracoes))


def test_checkpoint_carrega_apenas_linhas_novas(tmp_path):
    arquivo = tmp_path / "geo_map.csv"
    checkpoint = tmp_path / "state" / "geo_map.json"
    primeira = [_linha(), _linha(local="Guarulhos")]
    _escrever_csv(arquivo, primeira)

    lote1 = ler_lote_pendente(arquivo, checkpoint)
    assert len(lote1.linhas) == 2
    salvar_checkpoint(checkpoint, lote1)

    lote_vazio = ler_lote_pendente(arquivo, checkpoint)
    assert lote_vazio.linhas == []
    assert lote_vazio.inicio == 2

    with arquivo.open("a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=CAMPOS_GEO_MAP).writerow(_linha(local="Sorocaba"))
    lote2 = ler_lote_pendente(arquivo, checkpoint)
    assert len(lote2.linhas) == 1
    assert lote2.linhas[0]["local"] == "Sorocaba"


def test_checkpoint_detecta_csv_reiniciado(tmp_path):
    arquivo = tmp_path / "geo_map.csv"
    checkpoint = tmp_path / "geo_map.json"
    _escrever_csv(arquivo, [_linha(), _linha(local="Guarulhos")])
    lote_antigo = ler_lote_pendente(arquivo, checkpoint)
    salvar_checkpoint(checkpoint, lote_antigo)

    _escrever_csv(arquivo, [_linha(local="Sorocaba")])
    lote_novo = ler_lote_pendente(arquivo, checkpoint)
    assert len(lote_novo.linhas) == 1
    assert lote_novo.linhas[0]["local"] == "Sorocaba"
    assert lote_novo.geracao != lote_antigo.geracao


def test_job_id_permanece_igual_em_retry_com_novo_horario(tmp_path):
    arquivo = tmp_path / "geo_map.csv"
    _escrever_csv(arquivo, [_linha()])
    lote1 = ler_lote_pendente(arquivo, tmp_path / "sem_checkpoint.json")
    lote2 = ler_lote_pendente(arquivo, tmp_path / "sem_checkpoint.json")
    assert lote1.linhas[0]["hora_ingestao"] != lote2.linhas[0]["hora_ingestao"]
    assert job_id_lote(lote1) == job_id_lote(lote2)


def test_checkpoint_json_armazena_cursor_e_hash(tmp_path):
    arquivo = tmp_path / "geo_map.csv"
    checkpoint = tmp_path / "state.json"
    _escrever_csv(arquivo, [_linha()])
    lote = ler_lote_pendente(arquivo, checkpoint)
    salvar_checkpoint(checkpoint, lote)
    estado = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert estado["linhas_lidas"] == 1
    assert estado["hash_prefixo"] == lote.hash_prefixo


def test_csv_sem_registros_nao_gera_lote(tmp_path):
    arquivo = tmp_path / "geo_map.csv"
    arquivo.write_text("", encoding="utf-8")
    lote = ler_lote_pendente(arquivo, tmp_path / "checkpoint.json")
    assert lote.linhas == []
    assert lote.total_linhas == 0


def test_converter_related_queries_aplica_tipos_bigquery():
    linha = converter_related(_linha_related())
    assert linha["data_coleta"] == "2026-10-16"
    assert linha["posicao"] == 1
    assert linha["valor"] == "Aumento repentino"
    assert linha["valor_num"] == 166800.0
    assert linha["hora_ingestao"].endswith("+00:00")


def test_converter_related_queries_permite_valor_numerico_ausente():
    linha = converter_related(_linha_related(valor="Breakout", valor_num=""))
    assert linha["valor"] == "Breakout"
    assert linha["valor_num"] is None


@pytest.mark.parametrize(
    ("alteracoes", "mensagem"),
    [
        ({"data_coleta": "16/10/2026"}, "data_coleta inválida"),
        ({"posicao": "primeiro"}, "posicao inválida"),
        ({"valor_num": "muitos"}, "valor_num inválido"),
    ],
)
def test_converter_related_queries_rejeita_dados_invalidos(alteracoes, mensagem):
    with pytest.raises(ValueError, match=mensagem):
        converter_related(_linha_related(**alteracoes))


def test_related_queries_tem_checkpoint_independente(tmp_path):
    arquivo = tmp_path / "related_queries.csv"
    checkpoint = tmp_path / "state" / "related_queries.json"
    _escrever_related_csv(arquivo, [_linha_related()])
    lote = ler_related_pendente(arquivo, checkpoint)
    assert len(lote.linhas) == 1
    assert lote.linhas[0]["consulta"] == "como foi a entrevista do lula na globo"
    assert lote.linhas[0]["posicao"] == 1


def test_schema_related_queries_tem_tipos_e_campos_proprios():
    from ingestao.bigquery import SCHEMA_RELATED_QUERIES

    schema = dict(SCHEMA_RELATED_QUERIES)
    assert schema["data_coleta"] == "DATE"
    assert schema["posicao"] == "INT64"
    assert schema["valor"] == "STRING"
    assert schema["valor_num"] == "FLOAT64"
    assert schema["hora_ingestao"] == "TIMESTAMP"


def test_rotina_chama_coletor_antes_da_ingestao(monkeypatch):
    import datetime as dt
    import ingestao.rotina as rotina

    chamadas = []
    monkeypatch.setattr(rotina, "executar_cli_coletor", lambda args: chamadas.append(("coletor", args)) or 0)
    monkeypatch.setattr(
        rotina,
        "executar_geo_map",
        lambda *args: chamadas.append(("ingestao", *args)) or 0,
    )
    monkeypatch.setattr(
        rotina,
        "executar_related_queries",
        lambda: chamadas.append(("related_queries",)) or 0,
    )

    status = rotina.executar_coleta_e_ingestao(
        data=dt.date(2026, 10, 16), somente="estados", forcar=True
    )

    assert status == 0
    assert chamadas[0] == ("coletor", ["executar", "--data", "2026-10-16", "--somente", "estados", "--forcar"])
    assert chamadas[1][0] == "ingestao"
    assert chamadas[2] == ("related_queries",)


def test_status_de_falha_do_coletor_e_preservado_apos_ingestao(monkeypatch):
    import ingestao.rotina as rotina

    ordem = []
    monkeypatch.setattr(rotina, "executar_cli_coletor", lambda args: ordem.append("coletor") or 1)
    monkeypatch.setattr(rotina, "executar_geo_map", lambda *args: ordem.append("ingestao") or 0)
    monkeypatch.setattr(rotina, "executar_related_queries", lambda: ordem.append("related_queries") or 0)

    assert rotina.executar_coleta_e_ingestao() == 1
    assert ordem == ["coletor", "ingestao", "related_queries"]

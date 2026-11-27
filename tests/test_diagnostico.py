"""Verificação do ambiente e configuração robusta (sem rede: o acesso ao CNPq é simulado)."""
from __future__ import annotations

import importlib
import json
import os
import ssl
import sys
import urllib.error
import urllib.request

import pytest

from lattes_extrator import cli
from lattes_extrator import diagnostico as D
from lattes_extrator.config import Config, _validar


@pytest.fixture
def cfg(tmp_path):
    return Config(pasta_trabalho=str(tmp_path / "trabalho"))


def _por_nome(res: D.Resultado, trecho: str) -> D.Checagem:
    return next(c for c in res.checagens if trecho in c.nome)


# ------------------------------------------------------------------ caminho feliz
def test_ambiente_de_desenvolvimento_sem_erros(cfg):
    res = D.executar(cfg, rede=False)
    assert res.ok, D.texto(res)
    assert {c.nome for c in res.checagens} >= {"Arquivos do programa", "Pasta de trabalho",
                                                 "Automação do Chrome (Selenium)", "Banco de dados (SQLite FTS5)"}
    assert _por_nome(res, "RapidFuzz").status == D.OK
    assert all(c.segundos >= 0 for c in res.checagens)
    assert (cfg.raiz / "htmls").is_dir()


def test_selenium_confere_os_modulos_carregados_sob_demanda():
    c = D.checar_selenium()
    assert c.ok, c.detalhe
    assert c.detalhe.startswith("Selenium ")


# ------------------------------------------------------------- módulo faltando (exe)
def test_modulo_ausente_vira_erro_e_bloqueia_so_quem_usa(cfg, monkeypatch):
    original = importlib.import_module

    def falso(nome, *a, **k):
        if nome == "selenium.webdriver.chrome.options":
            raise ModuleNotFoundError("No module named 'selenium.webdriver.chrome.options'")
        return original(nome, *a, **k)

    monkeypatch.setattr(D.importlib, "import_module", falso)
    res = D.executar(cfg, rede=False)
    sel = _por_nome(res, "Selenium")
    assert sel.status == D.ERRO
    assert "selenium.webdriver.chrome.options" in sel.detalhe
    assert not res.ok
    assert res.bloqueia(D.NOMES) and res.bloqueia(D.COLETA)
    assert not res.bloqueia(D.PLANILHA) and not res.bloqueia(D.BASE)
    assert "problema" in res.resumo()


def test_checagem_que_explode_nao_derruba_as_outras(cfg, monkeypatch):
    def explode():
        raise RuntimeError("quebrou")

    res = D.executar(cfg, rede=False, extras=[explode])
    ultima = res.checagens[-1]
    assert ultima.status == D.ERRO and "quebrou" in ultima.detalhe
    assert len(res.checagens) > 5


def test_rapidfuzz_ausente_e_so_aviso(monkeypatch):
    monkeypatch.setitem(sys.modules, "rapidfuzz", None)
    c = D.checar_desempate()
    assert c.status == D.AVISO
    assert D.NOMES in c.afeta


# --------------------------------------------------------------- pasta de trabalho
@pytest.mark.skipif(sys.platform.startswith("win") or os.geteuid() == 0, reason="permissão de pasta POSIX")
def test_pasta_sem_escrita_vira_erro(tmp_path):
    raiz = tmp_path / "ro"
    raiz.mkdir()
    for sub in ("htmls", "planilhas"):
        (raiz / sub).mkdir()
    raiz.chmod(0o500)
    try:
        c = D.checar_pasta_trabalho(Config(pasta_trabalho=str(raiz)))
    finally:
        raiz.chmod(0o700)
    assert c.status == D.ERRO
    assert "Configurações" in c.dica


def test_pasta_em_nuvem_gera_aviso(tmp_path):
    c = D.checar_pasta_trabalho(Config(pasta_trabalho=str(tmp_path / "OneDrive" / "Extrator")))
    assert c.status == D.AVISO and "OneDrive" in c.detalhe


def test_pasta_inacessivel_volta_para_padrao(tmp_path, monkeypatch):
    arquivo = tmp_path / "nao-e-pasta"
    arquivo.write_text("x")
    padrao = tmp_path / "padrao"
    monkeypatch.setattr("lattes_extrator.config.pasta_trabalho_padrao", lambda: padrao)
    c = Config(pasta_trabalho=str(arquivo / "dentro"))
    aviso = c.garantir_pastas_ou_padrao()
    assert "não está acessível" in aviso
    assert c.raiz == padrao and (padrao / "htmls").is_dir()
    assert Config(pasta_trabalho=str(tmp_path / "ok")).garantir_pastas_ou_padrao() == ""


# ------------------------------------------------------------------ acesso ao CNPq
class _Resp:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_cnpq_respondendo(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _Resp())
    assert D.checar_cnpq().status == D.OK


@pytest.mark.parametrize("erro, esperado", [
    (urllib.error.URLError(OSError("Name or service not known")), D.AVISO),
    (urllib.error.HTTPError(D.URL_CNPQ, 503, "Service Unavailable", {}, None), D.AVISO),
    (TimeoutError("timed out"), D.AVISO),
    (urllib.error.URLError(ssl.SSLError(1, "handshake failure")), D.OK),
])
def test_cnpq_fora_do_ar_e_so_aviso(monkeypatch, erro, esperado):
    def falha(*a, **k):
        raise erro

    monkeypatch.setattr(urllib.request, "urlopen", falha)
    c = D.checar_cnpq(timeout=0.1)
    assert c.status == esperado
    assert set(c.afeta) == {D.COLETA, D.NOMES}


# ------------------------------------------------------------------ linha de comando
def test_cli_diagnostico_grava_json(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(Config, "carregar", classmethod(lambda cls: Config(pasta_trabalho=str(tmp_path / "t"))))
    saida = tmp_path / "diag.json"
    assert cli.main(["diagnostico", "--sem-rede", "--json", str(saida)]) == 0
    dados = json.loads(saida.read_text(encoding="utf-8"))
    assert dados["ok"] is True and dados["checagens"]
    assert "Selenium" in capsys.readouterr().out


# ------------------------------------------------------------- config.json robusto
@pytest.mark.parametrize("chave, valor, padrao, esperado", [
    ("processos", "abc", 0, 0),
    ("processos", 999, 0, 64),
    ("nota_minima", "0.7", 0.6, 0.7),
    ("nota_minima", -3, 0.6, 0.1),
    ("resultados_por_pagina", 30, 100, 100),
    ("resultados_por_pagina", "50", 100, 50),
    ("alerta_sonoro", "sim", True, True),
    ("alerta_sonoro", False, True, False),
    ("timeout_pagina", True, 30, 30),
    ("palavras_chave", "cbd", ["a"], ["a"]),
    ("palavras_chave", [" cbd ", "", 3], ["a"], ["cbd", "3"]),
    ("pasta_trabalho", "   ", "p", "p"),
])
def test_validar_config(chave, valor, padrao, esperado):
    assert _validar(chave, valor, padrao) == esperado


def test_config_corrompida_nao_derruba(tmp_path, monkeypatch):
    arq = tmp_path / "config.json"
    monkeypatch.setattr(Config, "arquivo", staticmethod(lambda: arq))
    arq.write_text("{ isso não é json", encoding="utf-8")
    assert Config.carregar() == Config()
    arq.write_text("[1, 2]", encoding="utf-8")
    assert Config.carregar() == Config()
    arq.write_text(json.dumps({"processos": "x", "atraso_entre_curriculos": 0, "desconhecida": 1}), encoding="utf-8")
    c = Config.carregar()
    assert c.processos == 0 and c.atraso_entre_curriculos == 1.0


def test_perfil_chrome_fora_da_pasta_de_trabalho_mas_respeita_o_antigo(tmp_path):
    c = Config(pasta_trabalho=str(tmp_path))
    assert tmp_path not in c.perfil_chrome.parents
    (tmp_path / ".chrome-perfil").mkdir()
    assert c.perfil_chrome == tmp_path / ".chrome-perfil"

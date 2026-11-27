"""Listagem do CNPq com erro do servidor ("N encontrados" mas sem os perfis)."""
from __future__ import annotations

import pytest

from lattes_extrator.config import Config
from lattes_extrator.eventos import Controle, Reporter
from lattes_extrator.navegador import (ESPERAS_LISTAGEM, ListagemComErro, NavegadorLattes, erro_listagem,
                                       parse_listagem)

CABECALHO = ('<div class="tit_form"> Resultado de 1 - 1 de <b>1</b> encontrado para: '
             "<b> 'Ana Beatriz Exemplo Vasconcelos' </b> </div>")
OK = (f"<html><body>{CABECALHO}<div class='resultado'><ol type='1' start='1'><li>"
      "<b><a href=\"javascript:abreDetalhe('K0000000A1','Ana_Beatriz',1,)\">Ana Beatriz Exemplo Vasconcelos</a></b>"
      " Doutora em Farmacologia</li></ol></div></body></html>")
STALE = (f"<html><body>{CABECALHO}<div class='resultado'><ol type='1' start='1'>"
         "<li>Stale file handle</li></ol></div></body></html>")
VAZIA = ("<html><body><div class='tit_form'>Nenhum resultado encontrado</div>"
         "<div class='resultado'></div></body></html>")


class DriverFalso:
    def __init__(self, paginas: list[str]) -> None:
        self.paginas = paginas
        self.page_source = ""
        self.cargas = 0

    def carregar(self) -> int:
        self.page_source = self.paginas[min(self.cargas, len(self.paginas) - 1)]
        self.cargas += 1
        return parse_listagem(self.page_source)[0]


class ReporterLista(Reporter):
    def __init__(self) -> None:
        self.msgs: list[tuple[str, str]] = []

    def log(self, msg: str, nivel: str = "info") -> None:
        self.msgs.append((msg, nivel))


@pytest.fixture
def nav(monkeypatch):
    n = NavegadorLattes(Config(), ReporterLista(), Controle())
    esperas: list[float] = []
    monkeypatch.setattr(n.ctl, "dormir", esperas.append)
    monkeypatch.setattr(n, "_esperar", lambda cond, timeout=None, intervalo=0.3: cond() or None)
    n.esperas = esperas
    return n


def test_listagem_normal_e_vazia_nao_tem_erro():
    assert parse_listagem(OK)[0] == 1 and len(parse_listagem(OK)[1]) == 1
    assert erro_listagem(OK) == ""
    assert erro_listagem(VAZIA) == ""


def test_detecta_erro_do_servidor_no_lugar_do_perfil():
    total, cands = parse_listagem(STALE)
    assert total == 1 and cands == []
    assert erro_listagem(STALE) == "Stale file handle"


def test_erro_intermitente_refaz_a_busca(nav):
    nav.driver = DriverFalso([STALE, STALE, OK])
    assert nav._listagem_valida(nav.driver.carregar, "na busca") == 1
    assert nav.driver.cargas == 3
    assert nav.esperas == list(ESPERAS_LISTAGEM[:2])
    avisos = [m for m, nivel in nav.rep.msgs if nivel == "aviso"]
    assert len(avisos) == 2 and "Stale file handle" in avisos[0]


def test_erro_persistente_vira_falha_e_nao_nao_encontrado(nav):
    nav.driver = DriverFalso([STALE])
    with pytest.raises(ListagemComErro, match="Stale file handle"):
        nav._listagem_valida(nav.driver.carregar, "na busca")
    assert nav.driver.cargas == len(ESPERAS_LISTAGEM) + 1


def test_sem_resultado_de_verdade_nao_repete(nav):
    nav.driver = DriverFalso([VAZIA])
    assert nav._listagem_valida(nav.driver.carregar, "na busca") == 0
    assert nav.driver.cargas == 1 and nav.esperas == []


def test_lista_que_so_demorou_a_aparecer_nao_refaz(nav, monkeypatch):
    nav.driver = DriverFalso([STALE])
    # na conferência extra a lista já apareceu: não precisa refazer a busca
    monkeypatch.setattr(nav, "_esperar", lambda cond, timeout=None, intervalo=0.3:
                        setattr(nav.driver, "page_source", OK) or cond())
    assert nav._listagem_valida(nav.driver.carregar, "na busca") == 1
    assert nav.driver.cargas == 1 and nav.esperas == []

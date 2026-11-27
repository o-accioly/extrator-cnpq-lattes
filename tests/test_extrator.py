"""Testes do núcleo (sem rede). Rodar com:  python -m pytest -q"""
from __future__ import annotations

import csv
from pathlib import Path

import openpyxl
import pytest

from lattes_extrator import jobs as J
from lattes_extrator.desempate import avaliar, decidir, identificar_coluna, similaridade_nome
from lattes_extrator.eventos import Reporter
from lattes_extrator.filtros import FiltrosBusca
from lattes_extrator.navegador import extrair_id16, parse_listagem, parse_preview
from lattes_extrator.parser import compilar_palavras, aplicar_palavras_chave, parse_curriculo
from lattes_extrator.planilhas import gerar_template, ler_planilha_nomes
from lattes_extrator.processamento import processar
from lattes_extrator.texto import decodificar_html, normalizar

# Currículo FICTÍCIO (tools/gerar_curriculo_ficticio.py): estrutura igual à do CNPq, dados inventados.
FIXTURE = Path(__file__).parent / "fixtures" / "1234567890123456.html"


class Mudo(Reporter):
    def log(self, *a, **k): pass
    def progresso(self, *a, **k): pass
    def etapa(self, *a, **k): pass


@pytest.fixture(scope="module")
def cv():
    return parse_curriculo(FIXTURE.read_bytes(), FIXTURE.stem)


# ------------------------------------------------------------------ texto
def test_decodifica_utf8_mesmo_com_meta_iso():
    html = '<meta charset="ISO-8859-1"><p>Formação</p>'.encode("utf-8")
    assert "Formação" in decodificar_html(html)


def test_decodifica_latin1_de_verdade():
    html = '<meta charset="ISO-8859-1"><p>Formação</p>'.encode("latin-1")
    assert "Formação" in decodificar_html(html)


def test_repara_mojibake():
    assert "Formação" in decodificar_html("Formação".encode("utf-8").decode("latin-1").encode("utf-8"))


def test_nao_estraga_maiusculas_com_til():
    assert decodificar_html("SÃO PAULO".encode("utf-8")) == "SÃO PAULO"


# ------------------------------------------------------------------ parser
def test_identificacao(cv):
    c = cv.campos
    assert c["ID Lattes"] == "1234567890123456"
    assert c["Código CNPq"] == "K0000000A1"
    assert c["Nome"] == "Ana Beatriz Exemplo Vasconcelos"
    assert c["ORCID"] == "https://orcid.org/0000-0002-1825-0097"
    assert c["Última atualização"] == "10/10/2026"
    assert c["Bolsa de produtividade"].startswith("Bolsista de Produtividade")


def test_formacao_e_atuacao(cv):
    c = cv.campos
    assert (c["Maior titulação"], c["Ano da maior titulação"]) == ("Doutorado", "1992")
    assert c["Instituição da maior titulação"].startswith("Université de Exemple")
    # vários vínculos "Atual": vale o de servidor/professor, não o de colaboradora
    assert c["Instituição atual"].startswith("Universidade Federal de Exemplo")


def test_artigos_e_totais(cv):
    """Regressão: os artigos em periódicos (div.artigo-completo) se perdiam."""
    c = cv.campos
    assert c["Qtd. artigos em periódicos"] == 120
    assert cv.contagens["Artigos completos publicados em periódicos"] == 120
    # 120 artigos + 6 livros + 30 capítulos + 15 trabalhos completos
    assert c["Produção bibliográfica (total)"] == 171
    artigos = cv.secoes["Artigos completos publicados em periódicos"]
    assert "VASCONCELOS, A. B. E." in artigos
    assert not artigos.startswith("VASCONCELOS, A. B. E.2025")   # sem os spans ocultos de ordenação
    assert "Citações:" not in artigos


def test_metricas(cv):
    assert cv.campos["Web of Science: citações"] == 1234
    assert cv.campos["Web of Science: fator H"] == 18
    assert cv.campos["Qtd. orientações concluídas"] == 60 and cv.campos["Qtd. orientações em andamento"] == 9


def test_secoes_mae_nao_duplicam(cv):
    """Regressão: "Bancas", "Orientações" repetiam todas as subseções."""
    assert len(cv.secoes.get("Bancas", "")) < 300
    assert "Orientações e supervisões concluídas > Dissertação de mestrado" in cv.secoes
    assert "Orientações e supervisões em andamento > Dissertação de mestrado" in cv.secoes


def test_nfc_preserva_ordinal(cv):
    assert "2º Lugar" in cv.secoes["Prêmios e títulos"]


def test_palavras_chave_texto_visivel(cv):
    r = aplicar_palavras_chave(cv, compilar_palavras(["cannabis", "cbd"], ["cbd"]))
    assert r["Contagem: cannabis"] > 10
    assert r["Contagem: cbd"] == 0           # sigla: não casa dentro de outras palavras
    assert "Projetos de pesquisa" in r["Ocorrências (colunas): cannabis"]


# --------------------------------------------------------------- navegador (HTML)
def test_extrair_id16():
    assert extrair_id16(FIXTURE.read_text(encoding="utf-8")) == "1234567890123456"


def test_parse_listagem():
    html = """<div class="tit_form">Resultados de 1 - 2 dos 2.392 encontrados</div>
    <div class="resultado"><ol><li><b><a href="javascript:abreDetalhe('K0000000A1','x',1,)">Ana Beatriz Exemplo Vasconcelos</a></b>
    Doutorado pelo Université de Exemple, França(1992)</li>
    <li><b><a href="javascript:abreDetalhe('K0000000B2','x',1,)">Maria Silva</a></b></li></ol></div>"""
    total, cands = parse_listagem(html)
    assert total == 2392
    assert [c.kid for c in cands] == ["K0000000A1", "K0000000B2"]
    assert "Exemple" in cands[0].resumo


def test_parse_preview():
    html = """<h1 class="name">Fulano</h1><p class="resumo">Doutor pela UFPE.</p> Certificado pelo autor em 08/11/2026
    <a onclick="abrirLink('http://lattes.cnpq.br/240.1/1234567890123456')">DGP</a>"""
    p = parse_preview(html)
    assert p["id16"] == "1234567890123456" and p["atualizado"] == "08/11/2026" and "UFPE" in p["resumo"]


# ------------------------------------------------------------------ filtros
def test_filtros_para_formulario():
    f = FiltrosBusca(modo="assunto", texto="cannabis", demais=True, formacao_uf="PE",
                     bolsa_categorias=["1A", "2"], atuacao_grande_area="40000001")
    d = f.para_formulario(100)
    assert d["campos"]["textoBusca"] == "cannabis"
    assert d["campos"]["filtros.categoriaNivelBolsa"] == "1A,2,"
    assert d["campos"]["filtros.buscaAtuacao"] == "true"
    assert d["checks"]["filtro0"] and d["checks"]["filtro2"] and d["checks"]["filtro4"]
    assert d["checks"]["buscarDemais"] and not d["checks"]["filtro9"]
    assert FiltrosBusca.de_dict(f.para_dict()) == f


# ------------------------------------------------------------------ desempate
def test_similaridade_nome():
    assert similaridade_nome("Ana Beatriz Exemplo Vasconcelos", "Ana Beatriz Exemplo Vasconcelos") == 100
    assert similaridade_nome("Maria Silva", "Maria da Silva") == 100          # "da" não conta
    assert similaridade_nome("Maria Silva Santos", "Maria Aparecida Silva Santos") == 90
    assert similaridade_nome("Maria da Silva Santos", "Maria Margarida da Silva Reis dos Santos Ferreira") < 88


def test_identificar_coluna():
    assert identificar_coluna("Instituição onde trabalha") == ("criterio", "inst_atual")
    assert identificar_coluna("uf") == ("criterio", "uf")
    assert identificar_coluna("Nome") is None


def test_avaliar_completo(cv):
    linha = cv.como_linha()
    bom = avaliar({"Instituição onde trabalha": "UFEX", "Formação (nível)": "Doutorado",
                   "UF / cidade de atuação": "PE"}, linha, "")
    ruim = avaliar({"Instituição onde trabalha": "Universidade de São Paulo", "Ano de formação": "2015"}, linha, "")
    assert bom.nota > 0.9 and ruim.nota < 0.5


def test_decidir_margem():
    class C:  # candidato qualquer
        pass
    a, b = C(), C()
    from lattes_extrator.desempate import Avaliacao
    assert decidir([(a, Avaliacao(0.9, {"x": 0.9})), (b, Avaliacao(0.5, {"x": 0.5}))], 0.6, 0.12)[0] is a
    assert decidir([(a, Avaliacao(0.8, {"x": 0.8})), (b, Avaliacao(0.75, {"x": 0.75}))], 0.6, 0.12)[0] is None


# ------------------------------------------------------------------ planilhas
def test_template_e_leitura(tmp_path):
    tpl = gerar_template(tmp_path / "t.xlsx")
    wb = openpyxl.load_workbook(tpl)
    assert wb.sheetnames == ["Nomes", "Como preencher", "Atributos"]
    cab = [c.value for c in wb["Nomes"][1]]
    assert cab[0] == "Nome" and "Instituição onde trabalha" in cab and "Resumo" in cab
    # linhas de exemplo intactas são ignoradas; nomes novos entram
    ws = wb["Nomes"]
    ws.append(["Fulano de Tal"])
    wb.save(tpl)
    pn = ler_planilha_nomes(tpl)
    assert [l["Nome"] for l in pn.linhas] == ["Fulano de Tal"]


def test_leitura_csv(tmp_path):
    p = tmp_path / "n.csv"
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Pesquisador", "UF", "Vazia"])
        w.writerow(["Ana", "SP", ""])
        w.writerow(["", "RJ", ""])
    pn = ler_planilha_nomes(p)
    assert pn.coluna_nome == "Pesquisador" and len(pn.linhas) == 1 and pn.criterios == ["UF"]


# ------------------------------------------------------------------ processamento + banco
def test_processar_gera_planilha(tmp_path):
    pasta = tmp_path / "htmls" / "teste - Doutores"
    pasta.mkdir(parents=True)
    for i in range(3):
        (pasta / f"{i}.html").write_bytes(FIXTURE.read_bytes())
    (pasta / "ruim.html").write_bytes(b"\x00\x01 nada")
    r = processar(sorted(pasta.glob("*.html")), tmp_path / "saida", palavras=["cannabis"], siglas=[],
                  processos=1, reporter=Mudo(), raiz=tmp_path / "htmls")
    assert r.ok == 4 or r.ok == 3  # o arquivo ruim vira linha vazia ou erro, mas não derruba o lote
    wb = openpyxl.load_workbook(r.xlsx, read_only=True)
    assert wb.sheetnames[:1] == ["Perfis"] and "Resumo" in wb.sheetnames and "Dicionário" in wb.sheetnames
    linhas = list(wb["Perfis"].iter_rows(values_only=True))
    cab = linhas[0]
    assert cab[:3] == ("Assunto", "Tipo da pesquisa", "ID Lattes")
    assert linhas[1][0] == "teste" and linhas[1][1] == "Doutores"
    # TSV mantém o texto completo (sem corte)
    tsv = r.tsv.read_text(encoding="utf-8-sig").splitlines()
    i = tsv[0].split("\t").index("Resumos publicados em anais de congressos")
    assert len(tsv[1].split("\t")[i]) > 32767


def test_banco_retomada(tmp_path):
    b = J.Banco(tmp_path / "x.db")
    job = b.criar(J.TIPO_BUSCA, "t", {"a": 1})
    assert b.adicionar_itens(job.id, [("K1", {}), ("K2", {}), ("K1", {})]) == 2
    b.marcar(job.id, "K1", J.FEITO, id16="1")
    assert b.chaves(job.id, J.FEITO) == {"K1"}
    assert b.recontar(job.id) == (2, 1, 0)
    b.atualizar(job.id, status=J.RODANDO)
    b.fechar()
    b2 = J.Banco(tmp_path / "x.db")          # reabrir: o que estava rodando vira "interrompida"
    assert b2.obter(job.id).status == J.CANCELADO


def test_normalizar():
    assert normalizar("  Formação ACADÊMICA/Titulação ") == "formacao academica titulacao"


# ------------------------------------------------------------------ base de currículos
def test_base_indexa_busca_e_deduplica(tmp_path):
    from lattes_extrator.base import BaseCurriculos
    for pasta in ("cannabis - Doutores", "outra - Busca por nomes"):
        d = tmp_path / "htmls" / pasta
        d.mkdir(parents=True)
        (d / "1234567890123456.html").write_bytes(FIXTURE.read_bytes())
    b = BaseCurriculos(tmp_path / "base.db")
    assert b.atualizar(tmp_path / "htmls") == (2, 0)
    assert b.atualizar(tmp_path / "htmls") == (0, 0)          # incremental: nada mudou
    assert b.total() == 1                                       # mesma pessoa em duas pastas
    r, n = b.buscar("farmaceutica exemple", ordem="relevancia")
    assert n == 1 and r[0].dados["nome"] == "Ana Beatriz Exemplo Vasconcelos" and len(r[0].outras_pastas) == 1
    assert b.buscar('"tecnologia farmaceutica"')[1] == 1       # frase exata, sem acento
    assert b.buscar("xyzinexistente")[1] == 0
    assert b.buscar("", pasta="cannabis - Doutores")[1] == 1
    (tmp_path / "htmls" / "outra - Busca por nomes" / "1234567890123456.html").unlink()
    assert b.atualizar(tmp_path / "htmls") == (0, 1)           # arquivo apagado sai do índice
    b.fechar()


def test_html_limpo_sem_menu_do_site():
    pytest.importorskip("PySide6")
    from lattes_extrator.gui.pagina_base import html_limpo
    h = html_limpo(FIXTURE.read_text(encoding="utf-8"))
    assert "Ana Beatriz Exemplo Vasconcelos" in h and "<script" not in h and "Busca Textual" not in h


def test_visualizador_prepara_html_offline():
    pytest.importorskip("PySide6")
    from lattes_extrator.gui.visualizador_cv import PASTA_WEB, converter_para_tabelas, preparar_para_webengine
    html = FIXTURE.read_text(encoding="utf-8")
    web = preparar_para_webengine(html)
    assert "<script" not in web.lower() and '<base href="file:' in web and '"/buscatextual/' not in web
    assert (PASTA_WEB / "css" / "style_curiculo.css").exists()          # estilos do CNPq empacotados
    tab = converter_para_tabelas(html)
    assert "Ana Beatriz Exemplo Vasconcelos" in tab and "<table" in tab and "Artigos completos publicados" in tab

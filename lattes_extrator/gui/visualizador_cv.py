"""Visualizador do currículo original (HTML salvo do Lattes) dentro do programa.

* Com QtWebEngine (pacote PySide6_WebEngine): mostra a página com as folhas de estilo e
  imagens do próprio CNPq, empacotadas em data/lattes_web (tools/baixar_estilo_lattes.py),
  sem depender de internet. Fica praticamente igual ao site.
* Sem QtWebEngine: converte o layout do Lattes (blocos flutuantes de 25%/75%, 8%/92%)
  em tabelas, que o QTextBrowser entende, com as mesmas cores e medidas do CSS do CNPq.
"""
from __future__ import annotations

import html as H
import re
import tempfile
from pathlib import Path

import lxml.html
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QTextCursor
from PySide6.QtWidgets import QTextBrowser, QVBoxLayout, QWidget

from ..filtros import _pasta_dados

PASTA_WEB = _pasta_dados() / "lattes_web"

try:  # motor web é opcional
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
    from PySide6.QtWebEngineWidgets import QWebEngineView
    TEM_WEBENGINE = True
except Exception:  # ImportError ou biblioteca do sistema faltando
    TEM_WEBENGINE = False


# ----------------------------------------------------------------- motor web
def preparar_para_webengine(html: str) -> str:
    """HTML salvo -> HTML que carrega os estilos locais e não executa scripts."""
    html = re.sub(r"<script\b.*?</script>", "", html, flags=re.S | re.I)
    # caminhos absolutos do site viram relativos à pasta local (que imita /buscatextual/)
    html = html.replace('"/buscatextual/', '"').replace("'/buscatextual/", "'")
    html = html.replace('url(/buscatextual/', 'url(')
    base = QUrl.fromLocalFile(str(PASTA_WEB) + "/").toString()
    extra = ("<style>body{background:#fff!important} .megamenu, #topo, .header-wrapper, .menu-header, "
             ".control-bar-wrapper, .rodape-cv, #rodape, .mini-menu-cv, .to-top-bar, .menu-cv-fixo"
             "{display:none!important} "
             # ordenação dos artigos depende de JavaScript (desligado aqui)
             "div:has(> .sub_tit_form #combo-ordenacao-citacao){display:none!important}</style>")
    if re.search(r"<head[^>]*>", html, re.I):
        html = re.sub(r"(<head[^>]*>)", rf'\1<meta charset="utf-8"><base href="{base}">', html, count=1, flags=re.I)
        html = re.sub(r"</head>", extra + "</head>", html, count=1, flags=re.I)
    else:
        html = f'<head><meta charset="utf-8"><base href="{base}">{extra}</head>' + html
    # o <meta charset> original (ISO-8859-1) contradiz o arquivo UTF-8 que gravamos
    html = re.sub(r'<meta[^>]+charset=["\']?iso-8859-1["\']?[^>]*>', "", html, flags=re.I)
    return html


if TEM_WEBENGINE:
    class _PaginaExterna(QWebEnginePage):
        """Cliques em links abrem no navegador do sistema; a página fica parada."""

        def acceptNavigationRequest(self, url, tipo, principal):
            if tipo == QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
                atual = self.url()
                # âncoras do menu do próprio currículo (#Formacao, #Producoes…) navegam aqui dentro
                if url.isLocalFile() and url.adjusted(QUrl.UrlFormattingOption.RemoveFragment) == \
                        atual.adjusted(QUrl.UrlFormattingOption.RemoveFragment):
                    return True
                QDesktopServices.openUrl(url)
                return False
            return True


# ----------------------------------------------------------------- modo tabela
CSS_TABELA = """
body { font-family: Arial, Helvetica, sans-serif; font-size: 13px; color: #333; background: #fff; }
h2.nome { color: #006699; font-size: 19px; font-weight: normal; margin: 8px 0 6px 0; }
.bolsa { color: #333; font-weight: bold; font-size: 13px; }
.info { color: #555; font-size: 12px; }
p.resumo { color: #666; font-size: 13px; line-height: 20px; text-align: justify; margin: 10px 0; }
h1 { color: #326C99; font-size: 18px; font-weight: normal; margin: 22px 0 4px 0; }
.inst { background: #006699; color: #fff; font-size: 12px; font-weight: bold; padding: 6px 10px; }
.cita { color: #326C99; font-size: 15px; margin: 14px 0 4px 0; }
td.rot { color: #333; font-weight: bold; text-align: right; vertical-align: top; padding: 4px 12px 4px 0; }
td.val { color: #333; vertical-align: top; padding: 4px 0; }
td.num { color: #333; font-weight: bold; text-align: right; vertical-align: top; padding: 4px 8px 4px 0; }
.metricas { border: 1px solid #A6C0D9; padding: 8px; }
a { color: #1F5FAD; }
"""


def _t(el) -> str:
    return re.sub(r"\s+", " ", " ".join(el.itertext())).strip()


def converter_para_tabelas(html: str) -> str:
    """Reconstrói o currículo com tabelas (mesma ordem e hierarquia do original)."""
    try:
        doc = lxml.html.fromstring(html)
    except Exception:
        return f"<pre>{H.escape(html[:200000])}</pre>"
    for el in doc.xpath("//script|//style|//noscript|//select"):
        el.drop_tree()
    for el in doc.xpath('//span[contains(@class,"informacao-artigo")]'):
        el.drop_tree()
    partes = [f"<html><head><style>{CSS_TABELA}</style></head><body>"]

    nomes = doc.xpath('//div[@class="infpessoa"]/h2')
    if nomes:
        partes.append(f"<h2 class='nome'>{H.escape(_t(nomes[0]))}</h2>")
        if len(nomes) > 1:
            partes.append(f"<div class='bolsa'>{H.escape(_t(nomes[1]))}</div>")
    for li in doc.xpath('//ul[@class="informacoes-autor"]/li'):
        partes.append(f"<div class='info'>• {H.escape(_t(li))}</div>")
    res = doc.xpath('//p[contains(@class,"resumo")]')
    if res:
        partes.append(f"<p class='resumo'>{H.escape(_t(res[0]))}</p>")

    def classes(el) -> set[str]:
        return set((el.get("class") or "").split())

    for wrapper in doc.xpath('//div[contains(concat(" ", normalize-space(@class), " "), " title-wrapper ")]'):
        h1 = wrapper.find(".//h1")
        titulo = _t(h1) if h1 is not None else ""
        if not titulo:
            continue
        partes.append(f"<h1>{H.escape(titulo)}</h1><hr color='#A6C0D9' size='1'>")
        linhas: list[str] = []
        rotulo = [None]

        def fechar():
            if linhas:
                partes.append("<table width='100%' cellspacing='0' cellpadding='0'>" + "".join(linhas) + "</table>")
                linhas.clear()

        def visitar(el):
            for f in el:
                if not isinstance(f.tag, str) or f.tag in ("h1", "script", "label"):
                    continue
                c = classes(f)
                if "inst_back" in c:
                    fechar()
                    partes.append(f"<table width='100%' cellspacing='0'><tr><td class='inst'>{H.escape(_t(f))}"
                                  "</td></tr></table>")
                elif "cita-artigos" in c:
                    fechar()
                    partes.append(f"<div class='cita'>{H.escape(_t(f))}</div>")
                elif "science_cont" in c:
                    fechar()
                    partes.append(f"<div class='metricas'>{H.escape(_t(f))}</div>")
                elif "layout-cell-3" in c:
                    rotulo[0] = _t(f)
                elif "layout-cell-9" in c:
                    linhas.append(f"<tr><td class='rot' width='25%'>{H.escape(rotulo[0] or '')}</td>"
                                  f"<td class='val'>{_conteudo(f)}</td></tr>")
                    rotulo[0] = None
                elif "layout-cell-1" in c:
                    rotulo[0] = _t(f)
                elif "layout-cell-11" in c:
                    linhas.append(f"<tr><td class='num' width='8%'>{H.escape(rotulo[0] or '')}</td>"
                                  f"<td class='val'>{_conteudo(f)}</td></tr>")
                    rotulo[0] = None
                elif "artigo-completo" in c:
                    visitar(f)
                elif f.tag == "pre":
                    fechar()
                    partes.append(f"<p class='resumo'>{H.escape(_t(f))}</p>")
                else:
                    visitar(f)

        visitar(wrapper)
        fechar()
    partes.append("</body></html>")
    return "".join(partes)


def _conteudo(el) -> str:
    """Texto do bloco mantendo links e quebras <br>."""
    for img in el.xpath(".//img"):
        img.drop_tree()
    for c in el.xpath('.//span[contains(@class,"citado")]'):
        c.drop_tree()
    try:
        s = lxml.html.tostring(el, encoding="unicode", method="html")
    except Exception:
        return H.escape(_t(el))
    s = re.sub(r"^<div[^>]*>|</div>$", "", s.strip())
    s = re.sub(r"</?(div|span)[^>]*>", "", s)
    return s


# ----------------------------------------------------------------- widget
class VisualizadorCV(QWidget):
    def __init__(self) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self._tmp: Path | None = None
        self.web = TEM_WEBENGINE and PASTA_WEB.exists()
        if self.web:
            self.view = QWebEngineView()
            self.view.setPage(_PaginaExterna(self.view))
            s = self.view.settings()
            s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, False)
            s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
            s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)  # foto do CNPq
            self.view.setStyleSheet("background: #FFFFFF;")
        else:
            self.view = QTextBrowser()
            self.view.setOpenExternalLinks(True)
            self.view.setStyleSheet("QTextBrowser { background: #FFFFFF; color: #222; border-radius: 10px; padding: 14px; }"
                                    "QScrollBar:vertical { background: #F1F4F7; width: 10px; }"
                                    "QScrollBar::handle:vertical { background: #C3CDD6; border-radius: 4px; }")
        lay.addWidget(self.view)

    @property
    def modo(self) -> str:
        return "web" if self.web else "tabelas"

    def carregar(self, html: str) -> None:
        if self.web:
            # setHtml tem limite de 2 MB: grava num arquivo temporário e carrega
            if self._tmp is None:
                self._tmp = Path(tempfile.gettempdir()) / "extrator-lattes-cv.html"
            self._tmp.write_text(preparar_para_webengine(html), encoding="utf-8")
            self.view.load(QUrl.fromLocalFile(str(self._tmp)))
        else:
            self.view.setHtml(converter_para_tabelas(html))

    def limpar(self) -> None:
        if self.web:
            self.view.setHtml("<html><body style='background:#fff'></body></html>")
        else:
            self.view.clear()

    def _achou(self, resultado) -> None:
        cb = getattr(self, "_callback_achar", None)
        if cb:
            cb(resultado.numberOfMatches() > 0)

    def achar(self, termo: str, callback=None) -> None:
        """Procura o próximo ``termo``; ``callback(bool)`` diz se encontrou."""
        if self.web:
            self._callback_achar = callback
            if not getattr(self, "_ligado", False):
                self.view.page().findTextFinished.connect(self._achou)
                self._ligado = True
            self.view.findText(termo)
            return
        ok = self.view.find(termo)
        if not ok:
            self.view.moveCursor(QTextCursor.MoveOperation.Start)
            ok = self.view.find(termo)
        if callback:
            callback(ok)

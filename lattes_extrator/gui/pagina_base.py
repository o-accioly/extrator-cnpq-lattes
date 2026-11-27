"""Base de currículos (busca em tudo que foi extraído) e tela de perfil."""
from __future__ import annotations

import html as H
import re
from pathlib import Path
from typing import TYPE_CHECKING

import lxml.html
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QTextCursor, QTextDocument
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QSizePolicy, QSplitter, QTableView, QTabWidget,
                               QTextBrowser, QVBoxLayout, QWidget)

from ..base import BaseCurriculos, Resultado
from ..eventos import Progresso, Reporter
from ..parser import aplicar_palavras_chave, compilar_palavras, parse_curriculo
from ..texto import decodificar_html, normalizar
from . import icones, tema
from .paginas import Pagina, abrir_local, limpar_layout, rolavel
from .visualizador_cv import VisualizadorCV
from .widgets import Card, GradeResponsiva, Spinner, Tile, botao, caixa_h, linha, rotulo

if TYPE_CHECKING:
    from .janela import JanelaPrincipal


# =========================================================================== índice
class _ReporterIndice(Reporter, QObject):
    andamento = Signal(int, int)

    def __init__(self) -> None:
        QObject.__init__(self)

    def log(self, *a, **k) -> None:
        pass

    def etapa(self, *a, **k) -> None:
        pass

    def progresso(self, p: Progresso, detalhe: str = "") -> None:
        self.andamento.emit(p.feitos, p.total)


class Indexador(QThread):
    """Atualiza o índice em segundo plano (só o que mudou)."""
    terminou = Signal(int, int)

    def __init__(self, base: BaseCurriculos, raiz: Path, processos: int) -> None:
        super().__init__()
        self.base, self.raiz, self.processos = base, raiz, processos
        self.rep = _ReporterIndice()

    def run(self) -> None:
        try:
            n, rem = self.base.atualizar(self.raiz, processos=self.processos, reporter=self.rep)
        except Exception:
            n, rem = 0, 0
        self.terminou.emit(n, rem)


# =========================================================================== tabela
class ModeloResultados(QAbstractTableModel):
    COLS = [("Nome", "nome"), ("Titulação", "titulacao"), ("Instituição atual", "inst_atual"),
            ("Pasta", "_pasta"), ("Artigos", "artigos"), ("Citações", "citacoes_wos"), ("Atualizado", "atualizacao")]

    def __init__(self) -> None:
        super().__init__()
        self.linhas: list[Resultado] = []

    def definir(self, linhas: list[Resultado]) -> None:
        self.beginResetModel()
        self.linhas = linhas
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.linhas)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.COLS)

    def headerData(self, sec, orient, role=Qt.ItemDataRole.DisplayRole):
        if orient == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.COLS[sec][0]
        return None

    def data(self, idx: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        r = self.linhas[idx.row()]
        chave = self.COLS[idx.column()][1]
        if role == Qt.ItemDataRole.DisplayRole:
            if chave == "_pasta":
                return r.pasta + (f"  +{len(r.outras_pastas)}" if r.outras_pastas else "")
            v = r.dados.get(chave)
            if chave == "titulacao" and v and r.dados.get("ano_titulacao"):
                return f"{v} ({r.dados['ano_titulacao']})"
            return "" if v is None else (f"{v:,}".replace(",", ".") if isinstance(v, int) else str(v))
        if role == Qt.ItemDataRole.ToolTipRole:
            if chave == "_pasta" and r.outras_pastas:
                return "Também em: " + ", ".join(r.outras_pastas)
            if chave == "nome":
                return r.dados.get("resumo", "")[:400]
            return None
        if role == Qt.ItemDataRole.ForegroundRole and chave != "nome":
            return QColor(tema.SUAVE)
        if role == Qt.ItemDataRole.FontRole and chave == "nome":
            from PySide6.QtGui import QFont
            f = QFont()
            f.setWeight(QFont.Weight.DemiBold)
            return f
        if role == Qt.ItemDataRole.TextAlignmentRole and chave in ("artigos", "citacoes_wos"):
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None


# =========================================================================== base
class PaginaBase(Pagina):
    def __init__(self, janela) -> None:
        super().__init__(janela)
        self.base: BaseCurriculos | None = None
        self.indexador: Indexador | None = None
        self.termo = ""

        topo = QWidget()
        th = QHBoxLayout(topo)
        th.setContentsMargins(0, 0, 0, 0)
        th.setSpacing(tema.ESP_S)
        self.spinner = Spinner(16)
        self.spinner.hide()
        self.l_indice = rotulo("", "suave")
        self.b_indexar = botao("Atualizar", None, self.indexar, "Procura currículos novos ou alterados", icone="refazer")
        th.addWidget(self.spinner)
        th.addWidget(self.l_indice)
        th.addWidget(self.b_indexar)
        self.cabecalho("Base de currículos", "Tudo o que já foi baixado, num só lugar. Pesquise por nome, instituição, "
                       "área ou qualquer termo do currículo.", topo)

        # barra de busca
        busca = QHBoxLayout()
        busca.setSpacing(tema.ESP_S)
        self.e_busca = QLineEdit()
        self.e_busca.setPlaceholderText("Pesquisar nome, instituição, área, tema…  (aspas para frase exata)")
        self.e_busca.addAction(icones.icone("busca", tema.SUAVE), QLineEdit.ActionPosition.LeadingPosition)
        self.e_busca.setClearButtonEnabled(True)
        self.e_busca.setMinimumHeight(40)
        self.e_busca.setStyleSheet("font-size: 10.5pt;")
        self.c_pasta = QComboBox()
        self.c_tit = QComboBox()
        self.c_ordem = QComboBox()
        for t, k in (("Relevância", "relevancia"), ("Nome", "nome"), ("Atualização mais recente", "atualizacao"),
                     ("Mais artigos", "artigos"), ("Mais citações", "citacoes")):
            self.c_ordem.addItem(t, k)
        for c, w in ((self.c_pasta, 220), (self.c_tit, 150), (self.c_ordem, 190)):
            c.setMinimumHeight(40)
            c.setMinimumWidth(w)
        busca.addWidget(self.e_busca, 1)
        busca.addWidget(self.c_pasta)
        busca.addWidget(self.c_tit)
        busca.addWidget(self.c_ordem)
        self.lay.addLayout(busca)

        # resultados + prévia
        self.divisor = QSplitter(Qt.Orientation.Horizontal)
        self.divisor.setChildrenCollapsible(False)
        self.divisor.setHandleWidth(tema.ESP_L)
        esq = QWidget()
        ev = QVBoxLayout(esq)
        ev.setContentsMargins(0, 0, 0, 0)
        ev.setSpacing(tema.ESP_S)
        self.modelo = ModeloResultados()
        self.tab = QTableView()
        self.tab.setModel(self.modelo)
        self.tab.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tab.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tab.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tab.verticalHeader().setVisible(False)
        self.tab.verticalHeader().setDefaultSectionSize(44)
        self.tab.setShowGrid(False)
        self.tab.setWordWrap(False)
        self.tab.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        hh = self.tab.horizontalHeader()
        hh.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        hh.setHighlightSections(False)
        hh.setStretchLastSection(False)
        self.tab.doubleClicked.connect(lambda *_: self.abrir_perfil())
        self.tab.selectionModel().currentRowChanged.connect(lambda *_: self._previa())
        ev.addWidget(self.tab, 1)
        self.l_contagem = rotulo("", "suave")
        ev.addWidget(self.l_contagem)
        self.vazio = Card()
        self.vazio.titulo("Nenhum currículo na base ainda",
                          "Quando você coletar pela busca ou por nomes, os currículos aparecem aqui automaticamente.")
        self.vazio.lay.addWidget(caixa_h(botao("Coletar pela busca", "primario",
                                               lambda: self.janela.abrir_assistente("busca"), icone="busca"),
                                         botao("Buscar por nomes", None, lambda: self.janela.abrir_assistente("nomes"),
                                               icone="nomes"), None))
        self.vazio.hide()
        ev.addWidget(self.vazio)
        self.divisor.addWidget(esq)

        self.previa = Card()
        self.previa.setMinimumWidth(320)
        self.previa.setMaximumWidth(420)
        self.p_corpo = QVBoxLayout()
        self.p_corpo.setSpacing(tema.ESP_M)
        self.previa.lay.addLayout(self.p_corpo, 1)
        self.divisor.addWidget(self.previa)
        self.divisor.setStretchFactor(0, 1)
        self.lay.addWidget(self.divisor, 1)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self.pesquisar)
        self.e_busca.textChanged.connect(lambda *_: self._timer.start())
        self.e_busca.returnPressed.connect(self.abrir_perfil)
        for c in (self.c_pasta, self.c_tit, self.c_ordem):
            c.currentIndexChanged.connect(lambda *_: self.pesquisar())
        self._previa()

    # ------------------------------------------------------------------ ciclo
    def _abrir_base(self) -> BaseCurriculos:
        caminho = self.cfg.raiz / "base.sqlite3"
        if self.base is None or getattr(self.base, "_caminho", None) != caminho:
            if self.base:
                self.base.fechar()
            self.base = BaseCurriculos(caminho)
            self.base._caminho = caminho  # type: ignore[attr-defined]
        return self.base

    def ao_mostrar(self) -> None:
        self._abrir_base()
        self._preencher_filtros()
        self.pesquisar()
        self.indexar()

    def filtrar_pasta(self, pasta: str) -> None:
        self._abrir_base()
        self._preencher_filtros()
        i = self.c_pasta.findData(pasta)
        if i >= 0:
            self.c_pasta.setCurrentIndex(i)

    def indexar(self) -> None:
        if self.indexador and self.indexador.isRunning():
            return
        base = self._abrir_base()
        self.indexador = Indexador(base, self.cfg.pasta_htmls, self.cfg.num_processos())
        self.indexador.rep.andamento.connect(self._andamento)
        self.indexador.terminou.connect(self._indexado)
        self.spinner.iniciar()
        self.b_indexar.setEnabled(False)
        self.l_indice.setText("Verificando currículos…")
        self.indexador.start()

    def _andamento(self, feitos: int, total: int) -> None:
        self.l_indice.setText(f"Indexando {feitos}/{total}…")
        if feitos % 50 == 0:
            self.pesquisar()

    def _indexado(self, n: int, removidos: int) -> None:
        self.spinner.parar()
        self.b_indexar.setEnabled(True)
        total = self.base.total() if self.base else 0
        msg = f"{total:,} pesquisadores".replace(",", ".")
        if n or removidos:
            msg += f" · {n} arquivo(s) indexado(s)" + (f", {removidos} removido(s)" if removidos else "")
        self.l_indice.setText(msg)
        self._preencher_filtros()
        self.pesquisar()

    def _preencher_filtros(self) -> None:
        if not self.base:
            return
        fac = self.base.facetas()
        for combo, itens, todos in ((self.c_pasta, fac["pastas"], "Todas as pastas"),
                                    (self.c_tit, fac["titulacoes"], "Toda titulação")):
            atual = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(todos, "")
            for nome, n in itens:
                combo.addItem(f"{nome}  ({n})", nome)
            i = combo.findData(atual)
            combo.setCurrentIndex(max(0, i))
            combo.blockSignals(False)

    # ------------------------------------------------------------------ busca
    def pesquisar(self) -> None:
        if not self.base:
            return
        self.termo = self.e_busca.text().strip()
        ordem = self.c_ordem.currentData()
        if ordem == "relevancia" and not self.termo:
            ordem = "nome"
        res, total = self.base.buscar(self.termo, pasta=self.c_pasta.currentData() or "",
                                      titulacao=self.c_tit.currentData() or "", ordem=ordem, limite=1000)
        self.modelo.definir(res)
        self._colunas()
        vazio_total = self.base.total() == 0 and not (self.indexador and self.indexador.isRunning())
        self.vazio.setVisible(vazio_total)
        self.tab.setVisible(not vazio_total)
        if total > len(res):
            self.l_contagem.setText(f"Mostrando {len(res)} de {total:,} resultados. Refine a busca para ver os demais."
                                    .replace(",", "."))
        else:
            self.l_contagem.setText(f"{total:,} resultado(s)".replace(",", ".") if self.termo or total else "")
        if res:
            self.tab.selectRow(0)
        self._previa()

    def _colunas(self) -> None:
        hh = self.tab.horizontalHeader()
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        larg = {0: 260, 1: 140, 3: 190, 4: 80, 5: 90, 6: 105}
        for c, w in larg.items():
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.Interactive)
            self.tab.setColumnWidth(c, w)
        w = self.tab.viewport().width()
        self.tab.setColumnHidden(3, w < 1000)
        self.tab.setColumnHidden(6, w < 860)
        self.tab.setColumnHidden(5, w < 760)
        self.tab.setColumnHidden(1, w < 600)

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self.previa.setVisible(self.width() >= 1150)
        self._colunas()

    def _selecionado(self) -> Resultado | None:
        i = self.tab.currentIndex()
        return self.modelo.linhas[i.row()] if i.isValid() and i.row() < len(self.modelo.linhas) else None

    def _previa(self) -> None:
        limpar_layout(self.p_corpo)
        r = self._selecionado()
        if r is None:
            l = rotulo("Selecione um pesquisador para ver o resumo aqui.", "suave", quebra=True)
            l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.p_corpo.addStretch()
            self.p_corpo.addWidget(l)
            self.p_corpo.addStretch()
            return
        d = r.dados
        self.p_corpo.addWidget(rotulo(r.pasta.upper(), "sobrelinha"))
        nome = rotulo(d.get("nome") or "(sem nome)", None, quebra=True)
        nome.setStyleSheet("font-size: 14pt; font-weight: 700;")
        self.p_corpo.addWidget(nome)
        sub = " · ".join(x for x in (d.get("titulacao"), d.get("inst_atual")) if x)
        if sub:
            self.p_corpo.addWidget(rotulo(sub, "suave", quebra=True))
        nums = QHBoxLayout()
        nums.setSpacing(tema.ESP_L)
        for rot, v in (("ARTIGOS", d.get("artigos")), ("CITAÇÕES", d.get("citacoes_wos")),
                       ("FATOR H", d.get("fator_h"))):
            col = QVBoxLayout()
            col.setSpacing(2)
            col.addWidget(rotulo(rot, "rotulo"))
            val = QLabel("—" if v is None else f"{v:,}".replace(",", "."))
            val.setStyleSheet("font-size: 14pt; font-weight: 700;")
            col.addWidget(val)
            nums.addLayout(col)
        nums.addStretch()
        self.p_corpo.addLayout(nums)
        if r.trecho and self.termo:
            t = H.escape(r.trecho).replace("[", f"<b style='color:{tema.AMARELO}'>").replace("]", "</b>")
            tl = QLabel(f"<span style='color:{tema.SUAVE}'>{t}</span>")
            tl.setWordWrap(True)
            tl.setStyleSheet(f"background: {tema.SUPERFICIE_2}; border-radius: 8px; padding: 10px;")
            self.p_corpo.addWidget(rotulo("ONDE APARECE", "rotulo"))
            self.p_corpo.addWidget(tl)
        if d.get("resumo"):
            self.p_corpo.addWidget(rotulo("RESUMO", "rotulo"))
            res = rotulo(d["resumo"][:420] + ("…" if len(d["resumo"]) > 420 else ""), "suave", quebra=True)
            self.p_corpo.addWidget(res)
        self.p_corpo.addStretch()
        self.p_corpo.addWidget(botao("Ver perfil completo", "primario", self.abrir_perfil, icone="detalhe"))
        acoes = QHBoxLayout()
        acoes.setSpacing(tema.ESP_S)
        if d.get("id16"):
            acoes.addWidget(botao("Lattes", None, lambda: QDesktopServices.openUrl(
                QUrl(f"http://lattes.cnpq.br/{d['id16']}")), "Abrir o currículo no site do CNPq", icone="externo"))
        acoes.addWidget(botao("HTML", None, lambda: abrir_local(r.arquivo), "Abrir o arquivo salvo no navegador",
                              icone="codigo"))
        self.p_corpo.addLayout(acoes)

    def abrir_perfil(self) -> None:
        r = self._selecionado()
        if r:
            self.janela.abrir_perfil(r.arquivo, self.termo)


# =========================================================================== perfil
def html_limpo(html: str) -> str:
    """HTML do Lattes sem scripts/estilos/imagens remotas, para o visualizador interno."""
    try:
        doc = lxml.html.fromstring(html)
    except Exception:
        return f"<pre>{H.escape(html[:200000])}</pre>"
    for el in doc.xpath("//script|//style|//noscript|//link|//iframe|//select|//img|//form//input"):
        el.drop_tree()
    # Só o miolo do currículo (sem o menu e o cabeçalho do site do CNPq)
    corpo = (doc.xpath("//div[contains(@class,'main-content')]//div[contains(@class,'layout-cell-pad-main')]")
             or doc.xpath("//body") or [doc])
    conteudo = lxml.html.tostring(corpo[0], encoding="unicode")
    estilo = ("body{font-family:Arial,Helvetica,sans-serif;font-size:10pt;color:#222;background:#fff}"
              "h1{color:#326C99;font-size:13pt;border-bottom:1px solid #ccd;margin-top:18px}"
              "h2{color:#1F4E79;font-size:15pt}b{color:#333}.inst_back{color:#1F4E79;font-weight:bold;margin-top:8px}"
              ".cita-artigos{color:#326C99;font-weight:bold;margin-top:10px}a{color:#1F5FAD}")
    return f"<html><head><style>{estilo}</style></head><body>{conteudo}</body></html>"


def destacar(texto: str, termo: str) -> str:
    t = H.escape(texto)
    for palavra in sorted({p for p in re.findall(r"\w{3,}", termo)}, key=len, reverse=True):
        t = re.sub(f"({re.escape(H.escape(palavra))})", rf"<span style='background:#5C4A12;color:#FFE28A'>\1</span>",
                   t, flags=re.I)
    return t


class PaginaPerfil(Pagina):
    rolar = False

    def __init__(self, janela) -> None:
        super().__init__(janela)
        self.arquivo = ""
        self.html = ""
        self.termo = ""
        voltar = botao("Base de currículos", "link", lambda: self.janela.ir("base"), icone="voltar")
        voltar.setStyleSheet("padding-left: 0;")
        self.lay.addWidget(voltar, 0, Qt.AlignmentFlag.AlignLeft)
        self.lay.addSpacing(-tema.ESP_S)

        topo = QHBoxLayout()
        topo.setSpacing(tema.ESP_L)
        v = QVBoxLayout()
        v.setSpacing(8)
        self.l_sobre = rotulo("", "sobrelinha")
        self.l_nome = rotulo("", "titulo")
        self.l_nome.setWordWrap(True)
        self.l_sub = rotulo("", "subtitulo", quebra=True)
        v.addWidget(self.l_sobre)
        v.addWidget(self.l_nome)
        v.addWidget(self.l_sub)
        topo.addLayout(v, 1)
        acoes = QHBoxLayout()
        acoes.setSpacing(tema.ESP_S)
        self.b_lattes = botao("Abrir no Lattes", "primario", self._lattes, icone="externo")
        self.b_html = botao("HTML no navegador", None, lambda: abrir_local(self.arquivo), icone="codigo")
        self.b_pasta = botao("", None, lambda: abrir_local(Path(self.arquivo).parent), "Abrir a pasta", icone="pasta")
        for b in (self.b_html, self.b_pasta, self.b_lattes):
            acoes.addWidget(b)
        topo.addLayout(acoes)
        self.lay.addLayout(topo)

        self.tiles = GradeResponsiva(largura_min=140, max_colunas=6, espaco=tema.ESP_M, colunas_validas=(6, 3, 2))
        self.t = {k: Tile(t, "—", s, c) for k, t, s, c in (
            ("art", "Artigos", "em periódicos", tema.VERDE), ("prod", "Produção", "bibliográfica total", tema.TEXTO),
            ("ori", "Orientações", "concluídas", tema.AZUL), ("cit", "Citações", "Web of Science", tema.ROXO),
            ("h", "Fator H", "Web of Science", tema.AMARELO), ("atu", "Atualizado", "no Lattes", tema.TEXTO))}
        for w in self.t.values():
            self.tiles.adicionar(w)
        self.lay.addWidget(self.tiles)

        self.abas = QTabWidget()
        self.abas.setDocumentMode(True)
        # visão geral
        self.geral = QWidget()
        self.g_lay = QVBoxLayout(self.geral)
        self.g_lay.setContentsMargins(0, tema.ESP_L, 2, tema.ESP_L)
        self.g_lay.setSpacing(tema.ESP_L)
        self.abas.addTab(rolavel(self.geral), "Visão geral")
        # seções
        sec = QWidget()
        sh = QHBoxLayout(sec)
        sh.setContentsMargins(0, tema.ESP_L, 0, 0)
        sh.setSpacing(tema.ESP_L)
        self.l_secoes = QListWidget()
        self.l_secoes.setFixedWidth(320)
        self.l_secoes.setWordWrap(True)
        self.l_secoes.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.l_secoes.setObjectName("ListaSecoes")
        self.l_secoes.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.l_secoes.currentRowChanged.connect(self._mostrar_secao)
        sh.addWidget(self.l_secoes)
        dir_ = QVBoxLayout()
        dir_.setSpacing(tema.ESP_S)
        self.e_filtro = QLineEdit()
        self.e_filtro.setPlaceholderText("Filtrar itens desta seção…")
        self.e_filtro.addAction(icones.icone("busca", tema.SUAVE), QLineEdit.ActionPosition.LeadingPosition)
        self.e_filtro.setClearButtonEnabled(True)
        self.e_filtro.textChanged.connect(lambda *_: self._mostrar_secao(self.l_secoes.currentRow()))
        dir_.addWidget(self.e_filtro)
        self.v_secao = QTextBrowser()
        self.v_secao.setOpenExternalLinks(True)
        dir_.addWidget(self.v_secao, 1)
        sh.addLayout(dir_, 1)
        self.abas.addTab(sec, "Seções do currículo")
        # original
        orig = QWidget()
        ov = QVBoxLayout(orig)
        ov.setContentsMargins(0, tema.ESP_L, 0, 0)
        ov.setSpacing(tema.ESP_S)
        bus = QHBoxLayout()
        self.e_achar = QLineEdit()
        self.e_achar.setPlaceholderText("Procurar no currículo (Enter = próximo)")
        self.e_achar.addAction(icones.icone("busca", tema.SUAVE), QLineEdit.ActionPosition.LeadingPosition)
        self.e_achar.returnPressed.connect(self._achar)
        self.l_achar = rotulo("", "suave")
        bus.addWidget(self.e_achar, 1)
        bus.addWidget(self.l_achar)
        ov.addLayout(bus)
        self.v_orig = VisualizadorCV()
        ov.addWidget(self.v_orig, 1)
        if not self.v_orig.web:
            bus.addWidget(rotulo("modo simplificado (instale PySide6_WebEngine para ver igual ao site)", "suave"))
        self.abas.addTab(orig, "Currículo original")
        self.abas.currentChanged.connect(self._aba)
        self.lay.addWidget(self.abas, 1)
        self._orig_carregado = False
        self.cv = None

    # ------------------------------------------------------------------
    def carregar(self, arquivo: str, termo: str = "") -> None:
        self.arquivo, self.termo = arquivo, termo
        dados = Path(arquivo).read_bytes()
        self.html = decodificar_html(dados)
        cv = parse_curriculo(self.html, Path(arquivo).stem)
        self.cv = cv
        c = cv.campos
        self.l_sobre.setText(Path(arquivo).parent.name.upper())
        self.l_nome.setText(c["Nome"] or Path(arquivo).stem)
        partes = [f"{c['Maior titulação']} ({c['Ano da maior titulação']})" if c["Ano da maior titulação"]
                  else c["Maior titulação"], c["Instituição atual"]]
        self.l_sub.setText(" · ".join(p for p in partes if p))
        self.b_lattes.setEnabled(bool(c["Link Lattes"]))

        def num(v):
            return "—" if v in ("", None) else f"{v:,}".replace(",", ".")
        self.t["art"].definir(num(c["Qtd. artigos em periódicos"]))
        self.t["prod"].definir(num(c["Produção bibliográfica (total)"]))
        self.t["ori"].definir(num(c["Qtd. orientações concluídas"]))
        self.t["cit"].definir(num(c["Web of Science: citações"]))
        self.t["h"].definir(num(c["Web of Science: fator H"]))
        self.t["atu"].definir(c["Última atualização"] or "—")

        self._montar_geral()
        self.l_secoes.clear()
        for nome, texto in cv.secoes.items():
            n = cv.contagens.get(nome)
            it = QListWidgetItem(nome)
            if n:
                it.setText(f"{nome}  ({n})")
            it.setData(Qt.ItemDataRole.UserRole, nome)
            it.setToolTip(nome)
            self.l_secoes.addItem(it)
        alvo = 0
        if termo:
            tn = normalizar(termo)
            for i, (nome, texto) in enumerate(cv.secoes.items()):
                if tn and all(p in normalizar(texto) for p in tn.split()):
                    alvo = i
                    break
        self.l_secoes.setCurrentRow(alvo)
        self._orig_carregado = False
        self.v_orig.limpar()
        self.e_achar.setText(termo.replace('"', ""))
        self.abas.setCurrentIndex(0)

    def _montar_geral(self) -> None:
        limpar_layout(self.g_lay)
        c = self.cv.campos
        ident = Card()
        ident.titulo("Identificação")
        grade = GradeResponsiva(largura_min=280, max_colunas=3, espaco=tema.ESP_M)
        for rot, v in (("ID Lattes", c["ID Lattes"]), ("Código CNPq", c["Código CNPq"]), ("ORCID", c["ORCID"]),
                       ("Nacionalidade", c["País de nacionalidade"]), ("Bolsa", c["Bolsa de produtividade"]),
                       ("Instituição da titulação", c["Instituição da maior titulação"]),
                       ("Endereço profissional", c["Endereço profissional"])):
            if not v:
                continue
            bl = QWidget()
            bv = QVBoxLayout(bl)
            bv.setContentsMargins(0, 0, 0, 0)
            bv.setSpacing(3)
            bv.addWidget(rotulo(rot.upper(), "rotulo"))
            val = rotulo(str(v), None, quebra=True)
            if str(v).startswith("http"):
                val.setText(f"<a style='color:{tema.AZUL}' href='{H.escape(str(v))}'>{H.escape(str(v))}</a>")
                val.setOpenExternalLinks(True)
            bv.addWidget(val)
            bv.addStretch()
            grade.adicionar(bl)
        ident.lay.addWidget(grade)
        self.g_lay.addWidget(ident)

        if c["Resumo"]:
            r = Card()
            r.titulo("Resumo")
            t = QLabel(destacar(c["Resumo"], self.termo) if self.termo else H.escape(c["Resumo"]))
            t.setWordWrap(True)
            t.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            t.setStyleSheet("line-height: 140%;")
            r.lay.addWidget(t)
            self.g_lay.addWidget(r)

        if c["Áreas de atuação"]:
            a = Card()
            a.titulo("Áreas de atuação")
            for item in c["Áreas de atuação"].split(" ; "):
                a.lay.addWidget(rotulo("•   " + item, "suave", quebra=True))
            self.g_lay.addWidget(a)

        if c["Atuação profissional"]:
            at = Card()
            at.titulo("Atuação profissional", "Vínculos agrupados por instituição")
            for bloco in c["Atuação profissional"].split(" | ")[:12]:
                inst, _, vinc = bloco.partition(": [")
                t = rotulo(inst, None, quebra=True)
                t.setStyleSheet("font-weight: 650;")
                at.lay.addWidget(t)
                for vv in vinc.rstrip("]").split("; ")[:6]:
                    if vv:
                        at.lay.addWidget(rotulo("    " + vv, "suave", quebra=True))
            self.g_lay.addWidget(at)

        pal = aplicar_palavras_chave(self.cv, compilar_palavras(self.cfg.palavras_chave, self.cfg.siglas_palavra_inteira))
        achadas = [(k[len("Contagem: "):], v) for k, v in pal.items() if k.startswith("Contagem: ") and v]
        pc = Card()
        pc.titulo("Palavras-chave", "As configuradas em Configurações, contadas neste currículo")
        if achadas:
            chips = GradeResponsiva(largura_min=150, max_colunas=6, espaco=tema.ESP_S)
            for p, n in sorted(achadas, key=lambda x: -x[1]):
                ch = QLabel(f"<b style='color:{tema.VERDE}'>{H.escape(p)}</b>  <span style='color:{tema.SUAVE}'>{n}×</span>")
                ch.setStyleSheet(f"background:{tema.mistura(tema.VERDE, 0.10)}; border:1px solid "
                                 f"{tema.mistura(tema.VERDE, 0.30)}; border-radius:10px; padding:6px 10px;")
                chips.adicionar(ch)
            pc.lay.addWidget(chips)
        else:
            pc.lay.addWidget(rotulo("Nenhuma das palavras-chave aparece neste currículo.", "suave"))
        self.g_lay.addWidget(pc)
        self.g_lay.addStretch()

    def _mostrar_secao(self, i: int) -> None:
        if i < 0 or not self.cv:
            self.v_secao.clear()
            return
        nome = self.l_secoes.item(i).data(Qt.ItemDataRole.UserRole)
        itens = [x for x in self.cv.secoes[nome].split(" ; ") if x.strip()]
        filtro = normalizar(self.e_filtro.text())
        if filtro:
            itens = [x for x in itens if all(p in normalizar(x) for p in filtro.split())]
        realce = " ".join(x for x in (self.e_filtro.text(), self.termo) if x)
        lis = "".join(f"<li style='margin-bottom:9px'>{destacar(x, realce) if realce else H.escape(x)}</li>" for x in itens)
        cab = (f"<h3 style='color:{tema.TEXTO}; margin:0 0 4px 0'>{H.escape(nome)}</h3>"
               f"<p style='color:{tema.SUAVE}; margin:0 0 12px 0'>{len(itens)} item(ns)</p>")
        self.v_secao.setHtml(f"<div style='color:{tema.TEXTO}; line-height:140%'>{cab}<ol>{lis}</ol></div>")

    def _aba(self, i: int) -> None:
        if i == 2 and not self._orig_carregado:
            self._orig_carregado = True
            self.v_orig.carregar(self.html)
            if self.e_achar.text():
                if self.v_orig.web:   # espera a página carregar para procurar
                    self.v_orig.view.loadFinished.connect(self._achar_uma_vez)
                else:
                    self._achar()

    def _achar_uma_vez(self, *_a) -> None:
        try:
            self.v_orig.view.loadFinished.disconnect(self._achar_uma_vez)
        except (RuntimeError, TypeError):
            pass
        self._achar()

    def _achar(self) -> None:
        termo = self.e_achar.text().strip()
        if termo:
            self.v_orig.achar(termo, lambda ok: self.l_achar.setText("" if ok else "não encontrado"))

    def _lattes(self) -> None:
        if self.cv and self.cv.campos["Link Lattes"]:
            QDesktopServices.openUrl(QUrl(str(self.cv.campos["Link Lattes"])))

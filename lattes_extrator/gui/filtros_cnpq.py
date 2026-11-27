"""Réplica da tela "Buscar Currículo Lattes" do CNPq.

Mesmos campos, mesma organização (busca simples, bases, nacionalidade e as dez
caixas de filtro que abrem uma janela com as opções). As opções vêm do catálogo
gerado a partir do próprio site (tools/atualizar_catalogo.py)."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QCompleter, QDialog, QFrame, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton, QRadioButton, QSpinBox, QVBoxLayout,
                               QWidget)

from ..filtros import FiltrosBusca, catalogo, opcoes
from . import tema


class Combo(QComboBox):
    """Combo pesquisável (digite parte do texto)."""

    def __init__(self, itens: list[dict], primeiro: str | None = None) -> None:
        super().__init__()
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setMaxVisibleItems(18)
        self.preencher(itens, primeiro)
        comp = QCompleter(self.model(), self)
        comp.setFilterMode(Qt.MatchFlag.MatchContains)
        comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comp.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.setCompleter(comp)
        self.lineEdit().editingFinished.connect(self._validar)

    def preencher(self, itens: list[dict], primeiro: str | None = None) -> None:
        self.blockSignals(True)
        self.clear()
        vistos = set()
        if primeiro is not None:
            self.addItem(primeiro, "0")
            vistos.add("0")
        for o in itens:
            if o["valor"] in vistos:
                continue
            vistos.add(o["valor"])
            self.addItem(o["texto"], o["valor"])
        self.setCurrentIndex(0)
        self.blockSignals(False)

    def _validar(self) -> None:
        i = self.findText(self.currentText(), Qt.MatchFlag.MatchFixedString)
        self.setCurrentIndex(i if i >= 0 else 0)

    def valor(self) -> str:
        v = self.currentData()
        return "0" if v is None else str(v)

    def definir(self, valor: str) -> None:
        i = self.findData(valor)
        self.setCurrentIndex(i if i >= 0 else 0)


def _rot(texto: str) -> QLabel:
    l = QLabel(texto)
    l.setProperty("cnpq", "rotulo")
    return l


class ModalFiltro(QDialog):
    """Janela de filtro no estilo das janelas do CNPq."""

    def __init__(self, titulo: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.setModal(True)
        self.setMinimumWidth(560)
        self.setStyleSheet(tema.QSS_CNPQ_MODAL)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 14)
        barra = QFrame()
        barra.setProperty("cnpq", "barra")
        bl = QHBoxLayout(barra)
        bl.setContentsMargins(16, 10, 16, 10)
        bl.addWidget(QLabel(titulo))
        lay.addWidget(barra)
        self.corpo = QGridLayout()
        self.corpo.setContentsMargins(20, 14, 20, 6)
        self.corpo.setHorizontalSpacing(12)
        self.corpo.setVerticalSpacing(10)
        lay.addLayout(self.corpo)
        rod = QHBoxLayout()
        rod.setContentsMargins(20, 6, 20, 0)
        self.b_limpar = QPushButton("Limpar")
        self.b_limpar.setProperty("cnpq", "sec")
        rod.addWidget(self.b_limpar)
        rod.addStretch()
        b_cancelar = QPushButton("Cancelar")
        b_cancelar.setProperty("cnpq", "sec")
        b_cancelar.clicked.connect(self.reject)
        b_ok = QPushButton("OK")
        b_ok.setDefault(True)
        b_ok.clicked.connect(self.accept)
        rod.addWidget(b_cancelar)
        rod.addWidget(b_ok)
        lay.addLayout(rod)

    def linha(self, i: int, rotulo: str, w: QWidget) -> None:
        self.corpo.addWidget(_rot(rotulo), i, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.corpo.addWidget(w, i, 1)


# ---------------------------------------------------------------- filtros
class _Filtro:
    """Uma das dez caixas: sabe abrir sua janela, ler/escrever nos FiltrosBusca e resumir."""
    titulo = ""

    def __init__(self, pagina: "PaginaCnpq") -> None:
        self.pagina = pagina

    def editar(self, f: FiltrosBusca) -> bool:
        dlg = ModalFiltro(self.titulo, self.pagina)
        self.montar(dlg, f)
        dlg.b_limpar.clicked.connect(lambda: (self.limpar(f), dlg.accept()))
        if dlg.exec() == QDialog.DialogCode.Accepted:
            if not getattr(self, "_limpou", False):
                self.aplicar(f)
            self._limpou = False
            return True
        return False

    def limpar(self, f: FiltrosBusca) -> None:
        for campo, padrao in self.campos_padrao().items():
            setattr(f, campo, padrao)
        self._limpou = True

    # a implementar
    def montar(self, dlg: ModalFiltro, f: FiltrosBusca) -> None: ...
    def aplicar(self, f: FiltrosBusca) -> None: ...
    def campos_padrao(self) -> dict: return {}


class FBolsaPQ(_Filtro):
    titulo = "Bolsistas de Produtividade do CNPq"
    CATS = ["1A", "1B", "1C", "1D", "2", "A", "B", "C"]

    def montar(self, dlg, f):
        self.checks = {}
        g1, g2 = QHBoxLayout(), QHBoxLayout()
        for c in self.CATS:
            cb = QCheckBox(c)
            cb.setChecked(c in f.bolsa_categorias)
            self.checks[c] = cb
            (g1 if c[0].isdigit() else g2).addWidget(cb)
        g1.addStretch()
        g2.addStretch()
        w1, w2 = QWidget(), QWidget()
        w1.setLayout(g1)
        w2.setLayout(g2)
        dlg.linha(0, "Produtividade em Pesquisa (PQ):", w1)
        dlg.linha(1, "Desenv. Tecnológico (DT):", w2)

    def aplicar(self, f):
        f.bolsa_categorias = [c for c, cb in self.checks.items() if cb.isChecked()]

    def campos_padrao(self):
        return {"bolsa_categorias": []}


class FBolsista(_Filtro):
    titulo = "Outros Bolsistas do CNPq"

    def montar(self, dlg, f):
        self.c = Combo(opcoes("modalidadeBolsa"), "Selecione a Modalidade de Bolsa")
        self.c.definir(f.bolsa_modalidade)
        dlg.linha(0, "Modalidade:", self.c)

    def aplicar(self, f):
        f.bolsa_modalidade = self.c.valor()

    def campos_padrao(self):
        return {"bolsa_modalidade": "0"}


class FFormacao(_Filtro):
    titulo = "Formação Acadêmica/Titulação"

    def montar(self, dlg, f):
        self.nivel = Combo([o for o in opcoes("nivelFormacao") if o["valor"] != "0"], "Todas")
        self.pais = Combo([o for o in opcoes("paises") if o["valor"] != "0"], "Todos")
        self.regiao = Combo([o for o in opcoes("regioes") if o["valor"] != "0"], "Todas")
        self.uf = Combo([o for o in opcoes("ufs") if o["valor"] != "0"], "Todas")
        self.inst = QLineEdit(f.formacao_instituicao)
        self.inst.setPlaceholderText("Nome da instituição")
        self.nivel.definir(f.formacao_nivel)
        self.pais.definir(f.formacao_pais)
        self.regiao.definir(f.formacao_regiao)
        self.uf.definir(f.formacao_uf)
        for i, (r, w) in enumerate((("Nível de formação:", self.nivel), ("País:", self.pais), ("Região:", self.regiao),
                                    ("UF:", self.uf), ("Instituição:", self.inst))):
            dlg.linha(i, r, w)

    def aplicar(self, f):
        f.formacao_nivel, f.formacao_pais = self.nivel.valor(), self.pais.valor()
        f.formacao_regiao, f.formacao_uf = self.regiao.valor(), self.uf.valor()
        f.formacao_instituicao = self.inst.text().strip()

    def campos_padrao(self):
        return {"formacao_nivel": "0", "formacao_pais": "0", "formacao_regiao": "0", "formacao_uf": "0",
                "formacao_instituicao": ""}


class FConceito(_Filtro):
    titulo = "Nível do Curso de Pós-graduação onde é Docente"

    def montar(self, dlg, f):
        h = QHBoxLayout()
        self.checks = {}
        for c in "1234567":
            cb = QCheckBox(f"Conceito {c}")
            cb.setChecked(c in f.conceito_curso)
            self.checks[c] = cb
            h.addWidget(cb)
        w = QWidget()
        w.setLayout(h)
        dlg.linha(0, "Conceito CAPES:", w)

    def aplicar(self, f):
        f.conceito_curso = [c for c, cb in self.checks.items() if cb.isChecked()]

    def campos_padrao(self):
        return {"conceito_curso": []}


class _Cascata:
    """Grande área > área > subárea > especialidade (árvore do catálogo)."""

    def __init__(self, niveis: int = 4) -> None:
        self.combos = [Combo([], "Todas") for _ in range(niveis)]
        self.combos[0].preencher(catalogo().get("areasAtuacao", []), "Todas")
        for i, c in enumerate(self.combos[:-1]):
            c.currentIndexChanged.connect(lambda _x, i=i: self._filhos(i))

    def _no(self, i: int):
        nos = catalogo().get("areasAtuacao", [])
        no = None
        for j in range(i + 1):
            v = self.combos[j].valor()
            no = next((n for n in nos if n["valor"] == v), None)
            if no is None:
                return None
            nos = no.get("filhos", [])
        return no

    def _filhos(self, i: int) -> None:
        no = self._no(i)
        self.combos[i + 1].preencher(no.get("filhos", []) if no else [], "Todas")
        for c in self.combos[i + 2:]:
            c.preencher([], "Todas")

    def definir(self, valores: list[str]) -> None:
        for i, v in enumerate(valores[:len(self.combos)]):
            self.combos[i].definir(v)
            if i + 1 < len(self.combos):
                self._filhos(i)

    def valores(self) -> list[str]:
        return [c.valor() for c in self.combos]


class FAtuacao(_Filtro):
    titulo = "Atuação Profissional (área de atuação)"

    def montar(self, dlg, f):
        self.cas = _Cascata(4)
        self.cas.definir([f.atuacao_grande_area, f.atuacao_area, f.atuacao_subarea, f.atuacao_especialidade])
        for i, (r, c) in enumerate(zip(("Grande área:", "Área:", "Subárea:", "Especialidade:"), self.cas.combos)):
            dlg.linha(i, r, c)

    def aplicar(self, f):
        f.atuacao_grande_area, f.atuacao_area, f.atuacao_subarea, f.atuacao_especialidade = self.cas.valores()

    def campos_padrao(self):
        return {"atuacao_grande_area": "0", "atuacao_area": "0", "atuacao_subarea": "0", "atuacao_especialidade": "0"}


class FOrientacao(_Filtro):
    titulo = "Atividade de Orientação"

    def montar(self, dlg, f):
        v = QVBoxLayout()
        self.checks = {}
        for cod, nome in catalogo().get("orientadorCNPq", {}).items():
            cb = QCheckBox(nome)
            cb.setChecked(cod in f.orientacao)
            self.checks[cod] = cb
            v.addWidget(cb)
        w = QWidget()
        w.setLayout(v)
        dlg.linha(0, "Orientador CNPq:", w)

    def aplicar(self, f):
        f.orientacao = [c for c, cb in self.checks.items() if cb.isChecked()]

    def campos_padrao(self):
        return {"orientacao": []}


class FIdioma(_Filtro):
    titulo = "Idioma"

    def montar(self, dlg, f):
        self.c = Combo([o for o in opcoes("idiomas") if o["valor"] != "0"], "Todos")
        self.c.definir(f.idioma)
        dlg.linha(0, "Idioma:", self.c)

    def aplicar(self, f):
        f.idioma = self.c.valor()

    def campos_padrao(self):
        return {"idioma": "0"}


class FProducao(_Filtro):
    titulo = "Áreas ou Setores da Produção em C&T"

    def montar(self, dlg, f):
        self.cas = _Cascata(2)
        self.cas.definir([f.producao_grande_area, f.producao_area])
        self.setor = Combo([o for o in opcoes("setoresProducao") if o["valor"] != "0"], "Todos")
        self.setor.definir(f.producao_setor)
        dlg.linha(0, "Grande área:", self.cas.combos[0])
        dlg.linha(1, "Área:", self.cas.combos[1])
        dlg.linha(2, "Setor de atividade:", self.setor)

    def aplicar(self, f):
        f.producao_grande_area, f.producao_area = self.cas.valores()
        f.producao_setor = self.setor.valor()

    def campos_padrao(self):
        return {"producao_grande_area": "0", "producao_area": "0", "producao_setor": "0"}


class FAtividade(_Filtro):
    titulo = "Atividade Profissional (Instituição)"

    def montar(self, dlg, f):
        self.pais = Combo([o for o in opcoes("paises") if o["valor"] != "0"], "Todos")
        self.regiao = Combo([o for o in opcoes("regioesAtividade") if o["valor"] != "0"], "Todas")
        self.uf = Combo([o for o in opcoes("ufsAtividade") if o["valor"] != "0"], "Todas")
        self.inst = QLineEdit(f.atividade_instituicao)
        self.inst.setPlaceholderText("Nome da instituição")
        self.nat = Combo([o for o in opcoes("naturezaAtividade") if o["valor"] != "0"], "Todas")
        self.atual = QCheckBox("Atividade atual?")
        self.atual.setChecked(f.atividade_atual)
        self.pais.definir(f.atividade_pais)
        self.regiao.definir(f.atividade_regiao)
        self.uf.definir(f.atividade_uf)
        self.nat.definir(f.atividade_natureza)
        for i, (r, w) in enumerate((("País:", self.pais), ("Região:", self.regiao), ("UF:", self.uf),
                                    ("Instituição:", self.inst), ("Natureza da atividade:", self.nat),
                                    ("", self.atual))):
            dlg.linha(i, r, w)

    def aplicar(self, f):
        f.atividade_pais, f.atividade_regiao, f.atividade_uf = self.pais.valor(), self.regiao.valor(), self.uf.valor()
        f.atividade_instituicao, f.atividade_natureza = self.inst.text().strip(), self.nat.valor()
        f.atividade_atual = self.atual.isChecked()

    def campos_padrao(self):
        return {"atividade_pais": "0", "atividade_regiao": "0", "atividade_uf": "0", "atividade_instituicao": "",
                "atividade_natureza": "0", "atividade_atual": False}


class FDGP(_Filtro):
    titulo = "Presença no Diretório de Grupos de Pesquisa"

    def montar(self, dlg, f):
        self.cb = QCheckBox("Pesquisador presente no Diretório de Grupos de Pesquisa")
        self.cb.setChecked(f.presente_dgp)
        dlg.linha(0, "", self.cb)

    def aplicar(self, f):
        f.presente_dgp = self.cb.isChecked()

    def campos_padrao(self):
        return {"presente_dgp": False}


# índice da caixa no site -> classe (esquerda: 0,2,4,6,8; direita: 1,3,5,7,9)
FILTROS = {0: FBolsaPQ, 1: FBolsista, 2: FFormacao, 3: FConceito, 4: FAtuacao,
           5: FOrientacao, 6: FIdioma, 7: FProducao, 8: FAtividade, 9: FDGP}


class PaginaCnpq(QFrame):
    """A tela de busca do CNPq, editável. ``obter()`` devolve os FiltrosBusca."""
    mudou = Signal()

    def __init__(self, modo_nomes: bool = False) -> None:
        super().__init__()
        self.setObjectName("CnpqPagina")
        self.setStyleSheet(tema.QSS_CNPQ)
        self.f = FiltrosBusca(modo="nome" if modo_nomes else "assunto",
                              demais=modo_nomes)
        self.modo_nomes = modo_nomes
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 16)
        lay.setSpacing(0)

        # barra do topo, como no site
        topo = QFrame()
        topo.setProperty("cnpq", "barra")
        tl = QHBoxLayout(topo)
        tl.setContentsMargins(18, 8, 18, 8)
        tl.addWidget(QLabel("CNPq · Plataforma Lattes"))
        tl.addStretch()
        tl.addWidget(QLabel("Busca Textual"))
        lay.addWidget(topo)

        corpo = QVBoxLayout()
        corpo.setContentsMargins(24, 16, 24, 0)
        corpo.setSpacing(10)
        lay.addLayout(corpo)
        t = QLabel("Buscar Currículo Lattes (Busca Simples)")
        t.setProperty("cnpq", "titulo")
        corpo.addWidget(t)

        # Buscar por
        caixa = QFrame()
        caixa.setProperty("cnpq", "caixa")
        g = QGridLayout(caixa)
        g.setContentsMargins(14, 12, 14, 12)
        g.setHorizontalSpacing(14)
        g.setVerticalSpacing(8)
        self.r_assunto = QRadioButton("Assunto (Título ou palavra chave da produção)")
        self.r_nome = QRadioButton("Nome")
        grupo = QButtonGroup(self)
        grupo.addButton(self.r_assunto)
        grupo.addButton(self.r_nome)
        self.texto = QLineEdit()
        self.texto.setPlaceholderText("Digite o termo da busca")
        self.l_buscar = QLabel("Buscar por:")
        self.l_buscar.setProperty("cnpq", "legenda")
        g.addWidget(self.l_buscar, 0, 0)
        hb = QHBoxLayout()
        hb.setSpacing(22)
        hb.addWidget(self.r_assunto)
        hb.addWidget(self.r_nome)
        hb.addStretch()
        g.addLayout(hb, 0, 1)
        g.addWidget(self.texto, 1, 1)
        self.aviso_nomes = QLabel("Os nomes vêm da sua planilha: cada linha vira uma busca por Nome com os filtros abaixo.")
        self.aviso_nomes.setProperty("cnpq", "ajuda")
        self.aviso_nomes.setWordWrap(True)
        g.addWidget(self.aviso_nomes, 2, 1)

        bases = QLabel("Nas bases:")
        bases.setProperty("cnpq", "legenda")
        g.addWidget(bases, 3, 0)
        self.c_dout = QCheckBox("Doutores")
        self.c_demais = QCheckBox("Demais pesquisadores (Mestres, Graduados, Estudantes, Técnicos, etc.)")
        hb2 = QHBoxLayout()
        hb2.setSpacing(22)
        hb2.addWidget(self.c_dout)
        hb2.addWidget(self.c_demais)
        hb2.addStretch()
        g.addLayout(hb2, 3, 1)

        nac = QLabel("Nacionalidade:")
        nac.setProperty("cnpq", "legenda")
        g.addWidget(nac, 4, 0)
        self.c_bra = QCheckBox("Brasileira")
        self.c_est = QCheckBox("Estrangeira")
        self.pais_nasc = Combo([o for o in opcoes("paisNascimento") if o["valor"] != "0"], "Todos")
        self.pais_nasc.setMinimumWidth(220)
        hb3 = QHBoxLayout()
        hb3.setSpacing(22)
        hb3.addWidget(self.c_bra)
        hb3.addWidget(self.c_est)
        hb3.addSpacing(16)
        lp = QLabel("País de nascimento:")
        hb3.addWidget(lp)
        hb3.addWidget(self.pais_nasc)
        hb3.addStretch()
        g.addLayout(hb3, 4, 1)
        g.setColumnStretch(1, 1)
        corpo.addWidget(caixa)

        # Filtros
        barra_f = QFrame()
        barra_f.setProperty("cnpq", "barra")
        bf = QHBoxLayout(barra_f)
        bf.setContentsMargins(12, 6, 12, 6)
        bf.addWidget(QLabel("Aplicar filtros"))
        bf.addStretch()
        self.b_limpar = QPushButton("Limpar filtros")
        self.b_limpar.setProperty("cnpq", "link")
        self.b_limpar.setStyleSheet("color: white;")
        self.b_limpar.clicked.connect(self._limpar_filtros)
        bf.addWidget(self.b_limpar)
        corpo.addSpacing(4)
        corpo.addWidget(barra_f)
        caixa_f = QFrame()
        caixa_f.setProperty("cnpq", "caixa")
        gf = QGridLayout(caixa_f)
        gf.setContentsMargins(14, 10, 14, 12)
        gf.setHorizontalSpacing(30)
        gf.setVerticalSpacing(4)
        self.caixas: dict[int, QCheckBox] = {}
        self.resumos: dict[int, QLabel] = {}
        self.filtros = {i: cls(self) for i, cls in FILTROS.items()}
        for i, filtro in self.filtros.items():
            col = i % 2
            lin = (i // 2) * 2
            cb = QCheckBox(filtro.titulo)
            cb.setCursor(Qt.CursorShape.PointingHandCursor)
            cb.clicked.connect(lambda _c, i=i: self._abrir(i))
            res = QLabel("")
            res.setProperty("cnpq", "ajuda")
            res.setWordWrap(True)
            res.setContentsMargins(26, 0, 0, 4)
            self.caixas[i], self.resumos[i] = cb, res
            gf.addWidget(cb, lin, col)
            gf.addWidget(res, lin + 1, col)
        corpo.addWidget(caixa_f)
        self.grade_filtros = gf

        # Preferências
        pref = QFrame()
        pref.setProperty("cnpq", "caixa")
        pl = QHBoxLayout(pref)
        pl.setContentsMargins(14, 8, 14, 8)
        lpref = QLabel("Preferências:")
        lpref.setProperty("cnpq", "legenda")
        pl.addWidget(lpref)
        pl.addWidget(QLabel("Somente currículos atualizados nos últimos"))
        self.meses = QSpinBox()
        self.meses.setRange(0, 600)
        self.meses.setSpecialValueText("qualquer data")
        self.meses.setSuffix(" meses")
        self.meses.setMinimumWidth(120)
        pl.addWidget(self.meses)
        pl.addStretch()
        corpo.addWidget(pref)

        for w in (self.r_assunto, self.r_nome, self.c_dout, self.c_demais, self.c_bra, self.c_est):
            w.toggled.connect(self._mudou)
        self.texto.textChanged.connect(self._mudou)
        self.meses.valueChanged.connect(self._mudou)
        self.pais_nasc.currentIndexChanged.connect(self._mudou)
        self.definir(self.f)

    def resizeEvent(self, e) -> None:
        # Em telas estreitas as dez caixas de filtro ficam numa coluna só
        uma = self.width() < 760
        if getattr(self, "_uma_coluna", None) != uma:
            self._uma_coluna = uma
            for i in self.caixas:
                self.grade_filtros.removeWidget(self.caixas[i])
                self.grade_filtros.removeWidget(self.resumos[i])
            for pos, i in enumerate(sorted(self.caixas)):
                lin, col = ((pos * 2, 0) if uma else ((i // 2) * 2, i % 2))
                self.grade_filtros.addWidget(self.caixas[i], lin, col)
                self.grade_filtros.addWidget(self.resumos[i], lin + 1, col)
        super().resizeEvent(e)

    # ------------------------------------------------------------------
    def _abrir(self, i: int) -> None:
        self.filtros[i].editar(self.f)
        self._atualizar_caixas()
        self.mudou.emit()

    def _limpar_filtros(self) -> None:
        for flt in self.filtros.values():
            flt.limpar(self.f)
            flt._limpou = False
        self._atualizar_caixas()
        self.mudou.emit()

    def _atualizar_caixas(self) -> None:
        ativos = self.f.caixas()
        resumo = {linha.split(":")[0]: linha for linha in self.f.resumo()}
        chaves = {0: "Bolsa de produtividade", 1: "Bolsista CNPq", 2: "Formação", 3: "Conceito do curso",
                  4: "Área de atuação", 5: "Orientação", 6: "Idioma", 7: "Produção C&T",
                  8: "Atividade profissional", 9: "Presente no Diretório de Grupos de Pesquisa"}
        for i, cb in self.caixas.items():
            cb.setChecked(ativos[i])
            txt = resumo.get(chaves[i], "")
            self.resumos[i].setText(txt.split(": ", 1)[-1] if txt else "")
            self.resumos[i].setVisible(bool(txt))

    def _mudou(self, *_a) -> None:
        f = self.f
        f.modo = "nome" if (self.modo_nomes or self.r_nome.isChecked()) else "assunto"
        f.texto = "" if self.modo_nomes else self.texto.text().strip()
        f.doutores, f.demais = self.c_dout.isChecked(), self.c_demais.isChecked()
        f.brasileiros, f.estrangeiros = self.c_bra.isChecked(), self.c_est.isChecked()
        f.pais_nascimento = self.pais_nasc.valor()
        f.atualizacao_meses = self.meses.value()
        self.mudou.emit()

    def definir(self, f: FiltrosBusca) -> None:
        self.f = f.copia()
        ws = (self.r_assunto, self.r_nome, self.c_dout, self.c_demais, self.c_bra, self.c_est, self.texto, self.meses,
              self.pais_nasc)
        for w in ws:
            w.blockSignals(True)
        self.r_nome.setChecked(self.f.modo == "nome")
        self.r_assunto.setChecked(self.f.modo != "nome")
        self.texto.setText(self.f.texto)
        self.c_dout.setChecked(self.f.doutores)
        self.c_demais.setChecked(self.f.demais)
        self.c_bra.setChecked(self.f.brasileiros)
        self.c_est.setChecked(self.f.estrangeiros)
        self.pais_nasc.definir(self.f.pais_nascimento)
        self.meses.setValue(int(self.f.atualizacao_meses or 0))
        for w in ws:
            w.blockSignals(False)
        for w in (self.r_assunto, self.r_nome, self.texto, self.l_buscar):
            w.setVisible(not self.modo_nomes)
        self.aviso_nomes.setVisible(self.modo_nomes)
        self._atualizar_caixas()

    def obter(self) -> FiltrosBusca:
        self._mudou()
        return self.f.copia()

    def validar(self) -> str:
        """Mensagem de erro ou ''."""
        f = self.obter()
        if not (f.doutores or f.demais):
            return "Marque pelo menos uma base: Doutores ou Demais pesquisadores."
        if not (f.brasileiros or f.estrangeiros):
            return "Marque pelo menos uma nacionalidade."
        if not self.modo_nomes and not f.texto and not any(f.caixas().values()):
            return "Digite um termo de busca ou aplique pelo menos um filtro."
        return ""

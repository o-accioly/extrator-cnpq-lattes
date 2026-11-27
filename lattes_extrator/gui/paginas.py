"""Páginas da janela principal."""
from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout,
                               QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMenu, QMessageBox, QPlainTextEdit, QProgressBar, QScrollArea,
                               QSizePolicy, QSpinBox, QStackedWidget, QTableWidget, QTableWidgetItem, QToolButton,
                               QVBoxLayout, QWidget)

from .. import busca_nomes, coleta
from .. import jobs as J
from ..config import PALAVRAS_CHAVE_PADRAO, Config
from ..filtros import FiltrosBusca
from ..planilhas import gerar_template, ler_planilha_nomes
from . import tema
from .filtros_cnpq import PaginaCnpq
from . import icones
from .widgets import (Banner, Card, CardForm, CardFuncao, GradeResponsiva, IndicadorPassos, LogView, Pill, ProgressoAnimado,
                      Spinner, Tile, botao, caixa_h, caixa_v, linha, rotulo)

if TYPE_CHECKING:
    from .janela import JanelaPrincipal


def abrir_local(caminho: str | Path) -> None:
    if caminho:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(caminho)))


def rolavel(w: QWidget) -> QScrollArea:
    s = QScrollArea()
    s.setWidgetResizable(True)
    s.setWidget(w)
    s.setFrameShape(QScrollArea.Shape.NoFrame)
    s.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    return s


def quando(ts: float) -> str:
    d = dt.datetime.fromtimestamp(ts)
    hoje = dt.date.today()
    if d.date() == hoje:
        return "hoje " + d.strftime("%H:%M")
    if (hoje - d.date()).days == 1:
        return "ontem " + d.strftime("%H:%M")
    return d.strftime("%d/%m/%Y %H:%M")


class Pagina(QWidget):
    """Base das páginas: conteúdo centralizado com largura máxima (telas largas não
    espalham tudo), margens que encolhem em janelas estreitas e rolagem opcional."""
    rolar = False

    def __init__(self, janela: "JanelaPrincipal") -> None:
        super().__init__()
        self.janela = janela
        self.miolo = QWidget()
        self.miolo.setMaximumWidth(tema.LARGURA_CONTEUDO)
        self.miolo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.lay = QVBoxLayout(self.miolo)
        self.lay.setContentsMargins(40, 32, 40, 28)
        self.lay.setSpacing(tema.ESP_L)
        faixa = QWidget()
        h = QHBoxLayout(faixa)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        h.addStretch(0)
        h.addWidget(self.miolo, 1)
        h.addStretch(0)
        externo = QVBoxLayout(self)
        externo.setContentsMargins(0, 0, 0, 0)
        if self.rolar:
            externo.addWidget(rolavel(faixa))
        else:
            externo.addWidget(faixa)

    def resizeEvent(self, e) -> None:
        # margens laterais proporcionais: 40px em telas normais, 24px nas estreitas
        m = 40 if self.width() >= 1100 else 24
        self.lay.setContentsMargins(m, 32 if self.height() > 720 else 22, m, 24)
        super().resizeEvent(e)

    @property
    def cfg(self) -> Config:
        return self.janela.cfg

    @property
    def banco(self) -> J.Banco:
        return self.janela.banco

    def ao_mostrar(self) -> None:
        pass

    def cabecalho(self, titulo: str, sub: str = "", direita: QWidget | None = None,
                  sobrelinha: str = "") -> QVBoxLayout:
        h = QHBoxLayout()
        h.setSpacing(tema.ESP_L)
        v = QVBoxLayout()
        v.setSpacing(8)
        if sobrelinha:
            v.addWidget(rotulo(sobrelinha.upper(), "sobrelinha"))
        v.addWidget(rotulo(titulo, "titulo"))
        if sub:
            v.addWidget(rotulo(sub, "subtitulo", quebra=True))
        h.addLayout(v, 1)
        if direita:
            h.addWidget(direita, 0, Qt.AlignmentFlag.AlignTop)
        self.lay.addLayout(h)
        self.lay.addSpacing(tema.ESP_S)   # respiro entre cabeçalho e conteúdo
        return v


# =========================================================================== início
class PaginaInicio(Pagina):
    rolar = True

    def __init__(self, janela) -> None:
        super().__init__(janela)
        self.cabecalho("Extrator CNPq Lattes",
                       "Colete, encontre e organize currículos da Plataforma Lattes em planilhas prontas para análise.")

        self.lay.addWidget(rotulo("O QUE VOCÊ QUER FAZER?", "rotulo"))
        cards = GradeResponsiva(largura_min=290, max_colunas=3, colunas_validas=(3, 1))
        dados = [
            ("busca", "Coletar pela busca do CNPq",
             "Monte a busca com os mesmos filtros do site (assunto, formação, área, instituição…) e baixe todos os "
             "currículos encontrados.", tema.VERDE),
            ("nomes", "Buscar por nomes",
             "Envie uma planilha com nomes. O programa acha cada perfil, desempata homônimos pelos critérios que você "
             "informar e extrai os dados.", tema.AZUL),
            ("planilha", "Gerar planilha dos currículos",
             "Transforme currículos já baixados numa planilha formatada, com filtros, contagens e palavras-chave.",
             tema.ROXO),
        ]
        for (ic, t, d, cor), chave in zip(dados, ("busca", "nomes", "processar")):
            c = CardFuncao(ic, t, d, cor)
            c.clicado.connect(lambda chave=chave: self.janela.abrir_assistente(chave))
            cards.adicionar(c)
        self.lay.addWidget(cards)
        self.lay.addSpacing(tema.ESP_S)

        self.lay.addWidget(rotulo("RESUMO", "rotulo"))
        tiles = GradeResponsiva(largura_min=190, max_colunas=4, espaco=tema.ESP_M, colunas_validas=(4, 2, 1))
        self.t_cvs = Tile("Currículos baixados", "—", "na pasta de trabalho", tema.VERDE)
        self.t_conc = Tile("Extrações concluídas", "—")
        self.t_and = Tile("Para continuar", "—", "pausadas ou interrompidas", tema.AMARELO)
        self.t_plan = Tile("Planilhas geradas", "—", "", tema.AZUL)
        for t in (self.t_cvs, self.t_conc, self.t_and, self.t_plan):
            tiles.adicionar(t)
        self.lay.addWidget(tiles)
        self.lay.addSpacing(tema.ESP_S)

        self.recentes = Card()
        self.recentes.titulo("Extrações recentes", "As cinco últimas. O histórico completo fica em Extrações.",
                             botao("Ver todas", "link", lambda: self.janela.ir("extracoes"), icone="seta"))
        self.lista = QVBoxLayout()
        self.lista.setSpacing(0)
        self.recentes.lay.addLayout(self.lista)
        self.lay.addWidget(self.recentes)

        rod = QHBoxLayout()
        rod.setSpacing(tema.ESP_M)
        self.l_pasta = rotulo("", "suave")
        self.l_pasta.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        rod.addWidget(rotulo("PASTA DE TRABALHO", "rotulo"))
        rod.addWidget(self.l_pasta, 1)
        rod.addWidget(botao("Abrir pasta", None, lambda: abrir_local(self.cfg.raiz), icone="pasta"))
        self.lay.addSpacing(tema.ESP_XS)
        self.lay.addLayout(rod)
        self.lay.addStretch()

    def ao_mostrar(self) -> None:
        jobs = self.banco.listar(200)
        n_cvs = sum(1 for _ in self.cfg.pasta_htmls.rglob("*.html")) if self.cfg.pasta_htmls.exists() else 0
        n_plan = sum(1 for _ in self.cfg.pasta_planilhas.glob("*.xlsx")) if self.cfg.pasta_planilhas.exists() else 0
        self.t_cvs.definir(f"{n_cvs:,}".replace(",", "."))
        self.t_conc.definir(str(sum(1 for j in jobs if j.status == J.CONCLUIDO)))
        self.t_and.definir(str(sum(1 for j in jobs if j.status in (J.PAUSADO, J.CANCELADO, J.ERRO))))
        self.t_plan.definir(str(n_plan))
        self.l_pasta.setText(str(self.cfg.raiz))
        limpar_layout(self.lista)
        if not jobs:
            vazio = rotulo("Nenhuma extração ainda. Escolha uma das funções acima para começar.", "suave")
            vazio.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vazio.setMinimumHeight(90)
            self.lista.addWidget(vazio)
        for i, j in enumerate(jobs[:5]):
            self.lista.addWidget(LinhaJob(j, self.janela, ultima=i == min(len(jobs), 5) - 1))


class LinhaJob(QWidget):
    """Uma extração na lista: colunas com largura fixa para tudo ficar alinhado."""

    def __init__(self, job: J.Job, janela: "JanelaPrincipal", ultima: bool = False) -> None:
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("LinhaJob")
        if not ultima:
            self.setStyleSheet(f"#LinhaJob {{ border-bottom: 1px solid {tema.BORDA}; }}")
        h = QHBoxLayout(self)
        h.setContentsMargins(2, 12, 2, 12)
        h.setSpacing(tema.ESP_L)
        ic = QLabel()
        ic.setFixedSize(34, 34)
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nome_ic = {"busca": "busca", "nomes": "nomes", "processar": "planilha"}.get(job.tipo, "arquivo")
        ic.setPixmap(icones.pixmap(nome_ic, tema.SUAVE, 17))
        ic.setStyleSheet(f"background: {tema.SUPERFICIE_2}; border-radius: 9px;")
        h.addWidget(ic)
        v = QVBoxLayout()
        v.setSpacing(3)
        t = rotulo(job.titulo)
        t.setStyleSheet("font-weight: 600;")
        v.addWidget(t)
        v.addWidget(rotulo(f"{job.rotulo_tipo} · {quando(job.atualizado)}", "suave"))
        h.addLayout(v, 1)

        rodando = janela.execucao_ativa() == job.id
        pill = Pill()
        if rodando:
            pill.definir("Em andamento", tema.VERDE, pulsar=True)
        else:
            pill.definir(job.rotulo_status, tema.COR_STATUS.get(job.status, tema.SUAVE))
        caixa_pill = QWidget()
        caixa_pill.setFixedWidth(130)
        cp = QHBoxLayout(caixa_pill)
        cp.setContentsMargins(0, 0, 0, 0)
        cp.addStretch()
        cp.addWidget(pill)
        h.addWidget(caixa_pill)

        prog = QWidget()
        prog.setFixedWidth(170)
        pv = QVBoxLayout(prog)
        pv.setContentsMargins(0, 0, 0, 0)
        pv.setSpacing(5)
        pb = QProgressBar()
        pb.setRange(0, 1000)
        pb.setValue(int(job.fracao * 1000))
        pb.setFixedHeight(6)
        pv.addWidget(pb)
        nums = rotulo(f"{job.feitos:,} de {job.total:,}".replace(",", ".") if job.total else "—", "suave")
        nums.setStyleSheet(f"color: {tema.APAGADO}; font-size: 8.5pt;")
        pv.addWidget(nums)
        h.addWidget(prog)

        acoes = QWidget()
        acoes.setFixedWidth(150)
        al = QHBoxLayout(acoes)
        al.setContentsMargins(0, 0, 0, 0)
        al.addStretch()
        if rodando:
            al.addWidget(botao("Acompanhar", None, lambda: janela.mostrar_execucao(job.id)))
        elif job.tipo != J.TIPO_PROCESSAR and job.status != J.CONCLUIDO:
            al.addWidget(botao("Continuar", "primario", lambda: janela.iniciar(job.id), icone="play"))
        elif job.saida and Path(job.saida).exists():
            al.addWidget(botao("Planilha", None, lambda: abrir_local(job.saida), icone="arquivo"))
        else:
            al.addWidget(botao("Detalhes", None, lambda: janela.mostrar_execucao(job.id)))
        h.addWidget(acoes)
        self.prog, self.acoes, self.caixa_pill = prog, acoes, caixa_pill

    def resizeEvent(self, e) -> None:
        # em larguras pequenas some a barra (o status e a ação continuam)
        self.prog.setVisible(self.width() > 640)
        super().resizeEvent(e)


# ======================================================================= assistentes
class Passo:
    def __init__(self, nome: str, widget: QWidget, validar=None, ao_entrar=None) -> None:
        self.nome, self.widget, self.validar, self.ao_entrar = nome, widget, validar, ao_entrar


class Assistente(Pagina):
    titulo = ""
    subtitulo = ""

    def __init__(self, janela) -> None:
        super().__init__(janela)
        voltar = botao("Início", "link", lambda: self.janela.ir("inicio"), icone="voltar")
        voltar.setStyleSheet("padding-left: 0;")
        self.lay.addWidget(voltar, 0, Qt.AlignmentFlag.AlignLeft)
        self.lay.addSpacing(-tema.ESP_S)
        self.cabecalho(self.titulo, self.subtitulo)
        self.passos = self.criar_passos()
        self.indicador = IndicadorPassos([p.nome for p in self.passos])
        self.lay.addWidget(self.indicador)
        self.lay.addSpacing(tema.ESP_S)
        self.pilha = QStackedWidget()
        for p in self.passos:
            self.pilha.addWidget(rolavel(p.widget))
        self.lay.addWidget(self.pilha, 1)
        self.lay.addWidget(linha())
        rod = QHBoxLayout()
        rod.setSpacing(tema.ESP_M)
        self.l_passo = rotulo("", "suave")
        rod.addWidget(self.l_passo)
        self.erro = rotulo("", None, quebra=True)
        self.erro.setStyleSheet(f"color: {tema.VERMELHO}; font-weight: 600;")
        rod.addWidget(self.erro, 1)
        self.b_voltar = botao("Voltar", None, self.voltar, icone="voltar")
        self.b_prox = botao("Próximo", "primario", self.avancar)
        self.b_prox.setLayoutDirection(Qt.LayoutDirection.RightToLeft)   # ícone à direita do texto
        self.b_prox.setMinimumWidth(170)
        rod.addWidget(self.b_voltar)
        rod.addWidget(self.b_prox)
        self.lay.addLayout(rod)
        self.ir_passo(0)

    def resizeEvent(self, e) -> None:
        self.indicador.compacto(self.width() < 1050)
        super().resizeEvent(e)

    def criar_passos(self) -> list[Passo]:
        raise NotImplementedError

    def reiniciar(self) -> None:
        self.ir_passo(0)

    def ir_passo(self, i: int) -> None:
        self.i = i
        self.pilha.setCurrentIndex(i)
        self.indicador.definir(i)
        self.erro.setText("")
        self.indicador.compacto(self.width() < 1050)
        self.l_passo.setText(f"Passo {i + 1} de {len(self.passos)}")
        self.b_voltar.setVisible(i > 0)
        ultimo = i == len(self.passos) - 1
        self.b_prox.setText("Iniciar extração" if ultimo else "Próximo")
        self.b_prox.setIcon(icones.icone("play" if ultimo else "seta", "#04130C", tamanho=16))
        if self.passos[i].ao_entrar:
            self.passos[i].ao_entrar()

    def voltar(self) -> None:
        if self.i > 0:
            self.ir_passo(self.i - 1)

    def avancar(self) -> None:
        p = self.passos[self.i]
        if p.validar:
            msg = p.validar()
            if msg:
                self.erro.setText(msg)
                return
        if self.i < len(self.passos) - 1:
            self.ir_passo(self.i + 1)
        else:
            try:
                job_id = self.iniciar()
            except Exception as e:
                self.erro.setText(str(e))
                return
            if job_id:
                self.janela.iniciar(job_id)

    def iniciar(self) -> str | None:
        raise NotImplementedError

    # ---- blocos comuns
    @staticmethod
    def explicacao(titulo: str, passos: list[tuple[str, str]], dicas: list[str], extra: QWidget | None = None) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, tema.ESP_S, 2, tema.ESP_S)
        v.setSpacing(tema.ESP_L)
        card = Card()
        card.titulo(titulo)
        card.lay.setSpacing(tema.ESP_L)
        for n, (t, d) in enumerate(passos, 1):
            h = QHBoxLayout()
            h.setSpacing(tema.ESP_L)
            num = QLabel(str(n))
            num.setFixedSize(30, 30)
            num.setAlignment(Qt.AlignmentFlag.AlignCenter)
            num.setStyleSheet(f"background:{tema.mistura(tema.VERDE, 0.15)}; color:{tema.VERDE}; border-radius:15px; font-weight:700;")
            h.addWidget(num, 0, Qt.AlignmentFlag.AlignTop)
            col = QVBoxLayout()
            col.setSpacing(4)
            tt = rotulo(t)
            tt.setStyleSheet("font-weight: 650;")
            col.addWidget(tt)
            col.addWidget(rotulo(d, "suave", quebra=True))
            h.addLayout(col, 1)
            card.lay.addLayout(h)
        v.addWidget(card)
        if dicas:
            c2 = Card()
            c2.titulo("Bom saber")
            c2.lay.setSpacing(tema.ESP_S)
            for d in dicas:
                c2.lay.addWidget(rotulo("•   " + d, "suave", quebra=True))
            v.addWidget(c2)
        if extra:
            v.addWidget(extra)
        v.addStretch()
        return w

    def revisao(self) -> tuple[QWidget, QVBoxLayout]:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, tema.ESP_S, 2, tema.ESP_S)
        v.setSpacing(tema.ESP_L)
        card = Card()
        card.titulo("Tudo certo?", "Confira antes de iniciar. Para mudar algo, use Voltar.")
        corpo = QVBoxLayout()
        corpo.setSpacing(10)
        card.lay.addLayout(corpo)
        v.addWidget(card)
        aviso = Card()
        aviso.titulo("Durante a coleta")
        aviso.lay.setSpacing(tema.ESP_S)
        for t in ("Uma janela do Chrome vai abrir: deixe-a aberta (pode minimizar).",
                  "Se o CNPq pedir verificação (captcha), o programa avisa com som e espera você resolver na janela do Chrome.",
                  "Dá para pausar ou interromper a qualquer momento e continuar depois de onde parou."):
            aviso.lay.addWidget(rotulo("•   " + t, "suave", quebra=True))
        v.addWidget(aviso)
        v.addStretch()
        return w, corpo

    def _item_filtro(self, linha_: str) -> None:
        k, sep, v = linha_.partition(": ")
        self.item_revisao(self.rev, k if sep else "Filtro", v if sep else linha_)

    @staticmethod
    def item_revisao(corpo: QVBoxLayout, chave: str, valor: str) -> None:
        h = QHBoxLayout()
        h.setSpacing(tema.ESP_L)
        k = rotulo(chave.upper(), "rotulo")
        k.setFixedWidth(200)
        k.setWordWrap(True)
        h.addWidget(k, 0, Qt.AlignmentFlag.AlignTop)
        h.addWidget(rotulo(valor, None, quebra=True), 1)
        corpo.addLayout(h)


def limpar_layout(lay) -> None:
    while lay.count():
        it = lay.takeAt(0)
        if it.widget():
            w = it.widget()
            w.hide()
            w.setParent(None)   # some na hora (deleteLater só age na volta ao laço de eventos)
            w.deleteLater()
        elif it.layout():
            limpar_layout(it.layout())


class AssistenteBusca(Assistente):
    titulo = "Coletar pela busca do CNPq"
    subtitulo = "Os mesmos filtros da busca do site. Todos os currículos encontrados são baixados e viram planilha."

    def criar_passos(self) -> list[Passo]:
        expl = self.explicacao("Como funciona", [
            ("Monte a busca", "Use a réplica da tela do CNPq: assunto, bases (doutores/demais) e os filtros de "
                              "formação, área, instituição, idioma, bolsa…"),
            ("O programa busca no site", "Abre o Chrome, aplica exatamente esses filtros no buscatextual.cnpq.br e "
                                         "percorre todas as páginas de resultado."),
            ("Baixa cada currículo", "Abre o currículo de cada pessoa, salva o HTML e registra o progresso. "
                                     "Se parar, continua de onde estava."),
            ("Gera a planilha", "No fim, extrai todos os campos e gera um Excel formatado (e um .txt para Power BI)."),
        ], ["O CNPq pode limitar acessos muito rápidos; o intervalo entre currículos (Configurações) evita bloqueios.",
            "Use \"Limite de perfis\" para um teste rápido antes de uma coleta grande."])
        self.cnpq = PaginaCnpq(modo_nomes=False)
        w_filtros = caixa_v(rotulo("Preencha como faria no site do CNPq. Clique numa caixa de filtro para ver as opções.",
                                   "suave", quebra=True), self.cnpq, espaco=10, margens=(0, tema.ESP_S, 2, tema.ESP_S))

        op = CardForm("Opções da coleta")
        self.e_titulo = QLineEdit()
        self.e_titulo.setPlaceholderText("ex.: Cannabis - Pernambuco")
        self.s_limite = QSpinBox()
        self.s_limite.setRange(0, 1_000_000)
        self.s_limite.setSpecialValueText("todos os encontrados")
        self.s_limite.setSuffix(" perfis")
        self.c_proc = QCheckBox("Gerar a planilha automaticamente no final")
        self.c_proc.setChecked(True)
        self.s_atraso = QDoubleSpinBox()
        self.s_atraso.setRange(1, 120)
        self.s_atraso.setSuffix(" s entre currículos")
        op.campo("Nome da extração", self.e_titulo, "Vira o nome da pasta dos currículos e da planilha.")
        op.campo("Limite de perfis", self.s_limite, "Use um número pequeno para testar antes de uma coleta grande.", 260)
        op.campo("Ritmo", self.s_atraso, "Intervalo entre um currículo e outro. Mais lento = menos bloqueios.", 260)
        op.campo("Ao terminar", self.c_proc)
        w_op = caixa_v(op, None, margens=(0, tema.ESP_S, 2, tema.ESP_S))

        self.w_rev, self.rev = self.revisao()
        return [
            Passo("Como funciona", expl),
            Passo("Filtros", w_filtros, self.cnpq.validar),
            Passo("Opções", w_op, self._validar_opcoes, self._entrar_opcoes),
            Passo("Revisão", self.w_rev, None, self._entrar_revisao),
        ]

    def _entrar_opcoes(self) -> None:
        f = self.cnpq.obter()
        if not self.e_titulo.text():
            self.e_titulo.setText(f.texto or "Coleta")
        self.s_atraso.setValue(self.cfg.atraso_entre_curriculos)

    def _validar_opcoes(self) -> str:
        return "" if self.e_titulo.text().strip() else "Dê um nome para a extração."

    def _entrar_revisao(self) -> None:
        limpar_layout(self.rev)
        f = self.cnpq.obter()
        self.item_revisao(self.rev, "Extração", self.e_titulo.text())
        for linha_ in f.resumo():
            self._item_filtro(linha_)
        self.item_revisao(self.rev, "Limite", self.s_limite.text())
        self.item_revisao(self.rev, "Pasta dos currículos",
                          str(self.cfg.pasta_htmls / f"{self.e_titulo.text()} - {coleta.categoria(f)}"))

    def iniciar(self) -> str:
        self.cfg.atraso_entre_curriculos = self.s_atraso.value()
        self.cfg.salvar()
        job = coleta.criar_job(self.banco, self.cfg, self.e_titulo.text().strip(), self.cnpq.obter(),
                               limite=self.s_limite.value(), processar_ao_final=self.c_proc.isChecked())
        return job.id


class AssistenteNomes(Assistente):
    titulo = "Buscar por nomes"
    subtitulo = "Uma planilha de nomes vira uma planilha de perfis Lattes, com link, confiança e todos os dados."

    def criar_passos(self) -> list[Passo]:
        self.planilha = None
        self.caminho = ""
        tpl = Card()
        tpl.titulo("Template da planilha")
        tpl.lay.addWidget(rotulo(
            "A coluna Nome é obrigatória. As outras são critérios de desempate: preencha só o que souber "
            "(formação, onde estudou, onde trabalha, estado, área, palavras-chave…). O template já traz todos os "
            "atributos que dá para extrair de um Lattes, com explicação em cada cabeçalho.", "suave", quebra=True))
        cols = QLabel("<b style='color:#FF8A80'>Nome</b> · Formação (nível) · Curso / área de formação · Instituição de "
                      "formação · Ano de formação · UF de formação · Área de atuação · Instituição onde trabalha · "
                      "UF / cidade de atuação · Palavras-chave · Nome em citações · ID Lattes · ORCID · …")
        cols.setWordWrap(True)
        cols.setStyleSheet(f"color:{tema.SUAVE}; background:{tema.SUPERFICIE_2}; border-radius:8px; padding:10px;")
        tpl.lay.addWidget(cols)
        tpl.lay.addWidget(caixa_h(botao("Baixar template (.xlsx)", "primario", self._baixar_template, icone="download"), None))
        expl = self.explicacao("Como funciona", [
            ("Busca cada nome no CNPq", "Com os filtros que você escolher (bases, formação, área…)."),
            ("Separa os homônimos", "Fica com os perfis de nome compatível; se houver nome idêntico, os aproximados saem."),
            ("Desempata pelos critérios", "Compara cada coluna da planilha com o trecho certo do currículo. Primeiro com "
                                          "o resumo da busca; se ainda empatar, abre o currículo completo dos melhores."),
            ("Entrega a planilha", "Status de cada linha (Encontrado, Desempatado, Verificar, Ambíguo, Não encontrado), "
                                   "link do Lattes, confiança, candidatos e os dados completos de quem foi encontrado."),
        ], ["Nomes completos dão resultados melhores.",
            "Linhas ambíguas trazem todos os candidatos (com link) na aba \"Candidatos\" para conferência rápida."], tpl)

        # passo planilha
        w_pl = QWidget()
        v = QVBoxLayout(w_pl)
        v.setContentsMargins(0, 6, 0, 6)
        escolha = Card()
        escolha.titulo("Sua planilha", "Excel (.xlsx) ou CSV, com uma coluna Nome. As outras colunas viram critérios.")
        self.l_arquivo = rotulo("Nenhum arquivo escolhido.", "suave")
        escolha.lay.addWidget(caixa_h(botao("Escolher planilha…", "primario", self._escolher, icone="arquivo"),
                                      self.l_arquivo, None, espaco=tema.ESP_L))
        v.addWidget(escolha)
        self.c_prev = Card()
        self.c_prev.titulo("Prévia")
        self.l_resumo = rotulo("", "suave", quebra=True)
        self.c_prev.lay.addWidget(self.l_resumo)
        self.tabela = QTableWidget()
        self.tabela.setMinimumHeight(220)
        self.tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.verticalHeader().setDefaultSectionSize(36)
        self.tabela.setShowGrid(False)
        self.tabela.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.tabela.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.tabela.horizontalHeader().setStretchLastSection(True)
        self.c_prev.lay.addWidget(self.tabela)
        self.c_prev.lay.addSpacing(tema.ESP_S)
        self.l_crit = rotulo("CRITÉRIOS DE DESEMPATE DETECTADOS", "rotulo")
        self.c_prev.lay.addWidget(self.l_crit)
        self.chips = GradeResponsiva(largura_min=230, max_colunas=4, espaco=tema.ESP_S)
        self.c_prev.lay.addWidget(self.chips)
        self.c_prev.hide()
        v.addWidget(self.c_prev)
        v.addStretch()

        self.cnpq = PaginaCnpq(modo_nomes=True)
        w_f = caixa_v(rotulo("Filtros aplicados em cada busca de nome. Deixe as duas bases marcadas para procurar "
                             "também mestres, graduados e estudantes.", "suave", quebra=True),
                      self.cnpq, espaco=10, margens=(0, tema.ESP_S, 2, tema.ESP_S))

        op = CardForm("Opções da busca")
        self.e_titulo = QLineEdit()
        self.c_cv = QCheckBox("Baixar o currículo completo e extrair todos os dados")
        self.c_cv.setChecked(True)
        self.s_cvs = QSpinBox()
        self.s_cvs.setRange(0, 20)
        self.s_cvs.setSuffix(" currículos")
        self.s_nota = QSpinBox()
        self.s_nota.setRange(10, 100)
        self.s_nota.setSuffix(" %")
        self.s_margem = QSpinBox()
        self.s_margem.setRange(0, 80)
        self.s_margem.setSuffix(" %")
        self.c_proc = QCheckBox("Gerar a planilha automaticamente no final")
        self.c_proc.setChecked(True)
        op.campo("Nome da extração", self.e_titulo, "Vira o nome da pasta e da planilha de resultado.")
        op.campo("Perfil encontrado", self.c_cv, "Sem isso, a planilha traz só o link e o status de cada nome.")
        op.campo("Desempate profundo", self.s_cvs, "Quando o resumo não basta, quantos currículos completos abrir "
                                                   "por nome empatado (0 = não abrir).", 200)
        op.campo("Confiança mínima", self.s_nota, "Nota mínima para aceitar um perfil.", 200)
        op.campo("Vantagem sobre o 2º", self.s_margem, "Quanto o 1º colocado precisa superar o 2º para não ficar "
                                                       "ambíguo.", 200)
        op.campo("Ao terminar", self.c_proc)
        w_op = caixa_v(op, None, margens=(0, tema.ESP_S, 2, tema.ESP_S))

        self.w_rev, self.rev = self.revisao()
        return [
            Passo("Como funciona", expl),
            Passo("Planilha", w_pl, self._validar_planilha),
            Passo("Filtros", w_f, self.cnpq.validar),
            Passo("Opções", w_op, lambda: "" if self.e_titulo.text().strip() else "Dê um nome para a extração.",
                  self._entrar_opcoes),
            Passo("Revisão", self.w_rev, None, self._entrar_revisao),
        ]

    def _baixar_template(self) -> None:
        destino, _ = QFileDialog.getSaveFileName(self, "Salvar template", str(Path.home() / "template busca por nomes.xlsx"),
                                                 "Excel (*.xlsx)")
        if destino:
            gerar_template(destino)
            abrir_local(destino)

    def _escolher(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(self, "Planilha de nomes", str(Path.home()),
                                                 "Planilhas (*.xlsx *.xlsm *.csv *.txt)")
        if caminho:
            self.carregar(caminho)

    def carregar(self, caminho: str) -> None:
        try:
            pn = ler_planilha_nomes(caminho)
        except Exception as e:
            self.erro.setText(str(e))
            return
        self.planilha, self.caminho = pn, caminho
        self.l_arquivo.setText(Path(caminho).name)
        cols = [pn.coluna_nome] + pn.criterios
        self.tabela.setColumnCount(len(cols))
        self.tabela.setHorizontalHeaderLabels(cols)
        mostrar = pn.linhas[:12]
        self.tabela.setRowCount(len(mostrar))
        for i, l in enumerate(mostrar):
            for j, c in enumerate(cols):
                self.tabela.setItem(i, j, QTableWidgetItem(l.get(c, "")))
        self.tabela.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tabela.resizeColumnsToContents()
        self.l_resumo.setText(f"{len(pn.linhas)} nomes encontrados na coluna \"{pn.coluna_nome}\"."
                              + (" Mostrando os 12 primeiros." if len(pn.linhas) > 12 else ""))
        for w in self.chips.itens:
            w.deleteLater()
        self.chips.itens.clear()
        if pn.criterios:
            self.l_crit.setText("CRITÉRIOS DE DESEMPATE DETECTADOS")
            for c, tipo in pn.descrever_criterios():
                n = sum(1 for l in pn.linhas if l.get(c))
                chip = QLabel(f"<b style='color:{tema.AZUL}'>{c}</b><br>"
                              f"<span style='color:{tema.SUAVE}; font-size:8.5pt'>{tipo} · preenchido em {n} "
                              f"de {len(pn.linhas)}</span>")
                chip.setStyleSheet(f"background: {tema.mistura(tema.AZUL, 0.10)}; border: 1px solid "
                                   f"{tema.mistura(tema.AZUL, 0.30)}; border-radius: 10px; padding: 8px 12px;")
                self.chips.adicionar(chip)
        else:
            self.l_crit.setText("NENHUM CRITÉRIO ALÉM DO NOME: HOMÔNIMOS FICARÃO COMO \"AMBÍGUO\"")
        self.c_prev.show()
        self.erro.setText("")

    def _validar_planilha(self) -> str:
        if not self.planilha:
            return "Escolha a planilha com os nomes."
        return ""

    def _entrar_opcoes(self) -> None:
        if not self.e_titulo.text() and self.caminho:
            self.e_titulo.setText(Path(self.caminho).stem)
        self.s_cvs.setValue(self.cfg.max_candidatos_cv)
        self.s_nota.setValue(int(self.cfg.nota_minima * 100))
        self.s_margem.setValue(int(self.cfg.margem_desempate * 100))

    def _entrar_revisao(self) -> None:
        limpar_layout(self.rev)
        pn = self.planilha
        self.item_revisao(self.rev, "Extração", self.e_titulo.text())
        self.item_revisao(self.rev, "Planilha", f"{Path(self.caminho).name} · {len(pn.linhas)} nomes")
        self.item_revisao(self.rev, "Critérios", ", ".join(pn.criterios) or "nenhum (só o nome)")
        for linha_ in self.cnpq.obter().resumo():
            self._item_filtro(linha_)
        self.item_revisao(self.rev, "Currículo completo", "sim" if self.c_cv.isChecked() else "não (só o link)")
        self.item_revisao(self.rev, "Desempate", f"confiança ≥ {self.s_nota.value()}%, vantagem ≥ {self.s_margem.value()}%, "
                                                 f"até {self.s_cvs.value()} currículos completos por empate")

    def iniciar(self) -> str:
        self.cfg.max_candidatos_cv = self.s_cvs.value()
        self.cfg.nota_minima = self.s_nota.value() / 100
        self.cfg.margem_desempate = self.s_margem.value() / 100
        self.cfg.salvar()
        job = busca_nomes.criar_job(self.banco, self.cfg, self.e_titulo.text().strip(), self.caminho,
                                    self.cnpq.obter(), baixar_cv=self.c_cv.isChecked(),
                                    processar_ao_final=self.c_proc.isChecked())
        return job.id


class AssistenteProcessar(Assistente):
    titulo = "Gerar planilha dos currículos"
    subtitulo = "Lê os HTMLs já baixados e gera um Excel formatado, com um .txt completo para Power BI."

    def criar_passos(self) -> list[Passo]:
        expl = self.explicacao("Como funciona", [
            ("Escolha as pastas", "Cada coleta salva os currículos numa pasta \"assunto - base\". Marque as que quiser juntar."),
            ("Extração em paralelo", "Usa todos os núcleos do computador; a memória fica constante mesmo com milhares de arquivos."),
            ("Planilha pronta", "Uma linha por pesquisador: identificação, formação, atuação, contagens de produção, métricas "
                                "de citação, palavras-chave e todas as seções do currículo."),
        ], ["As colunas \"Assunto\" e \"Tipo da pesquisa\" vêm do nome da pasta.",
            "Células acima do limite do Excel (32.767 caracteres) são cortadas com aviso; o .txt guarda o texto completo."])
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, tema.ESP_S, 2, tema.ESP_S)
        c = Card()
        c.titulo("Pastas com currículos", "Cada coleta fica numa pasta \"assunto - base\". Marque as que vão para a planilha.",
                 caixa_h(botao("Marcar todas", "link", lambda: self._marcar(True)),
                         botao("Desmarcar", "link", lambda: self._marcar(False)), espaco=0))
        self.lista = QListWidget()
        self.lista.setMinimumHeight(240)
        self.lista.setSpacing(2)
        c.lay.addWidget(self.lista)
        c.lay.addWidget(caixa_h(botao("Adicionar outra pasta…", None, self._adicionar, icone="pasta"), None))
        v.addWidget(c)
        v.addStretch()

        op = CardForm("Opções da planilha")
        self.e_titulo = QLineEdit("Compilação")
        self.t_palavras = QPlainTextEdit()
        self.t_palavras.setMinimumHeight(170)
        self.t_palavras.setPlaceholderText("uma palavra por linha")
        op.campo("Nome da planilha", self.e_titulo)
        op.campo("Palavras-chave", self.t_palavras, "Uma por linha. Para cada uma: quantas vezes aparece no currículo "
                                                    "e em quais colunas. Sem acento e sem diferenciar maiúsculas.")
        w_op = caixa_v(op, None, margens=(0, tema.ESP_S, 2, tema.ESP_S))
        self.w_rev, self.rev = self.revisao()
        self.w_rev.layout().itemAt(1).widget().hide()  # sem Chrome aqui
        return [
            Passo("Como funciona", expl),
            Passo("Currículos", w, self._validar, self._carregar_pastas),
            Passo("Opções", w_op, None, lambda: self.t_palavras.setPlainText("\n".join(self.cfg.palavras_chave))
                  if not self.t_palavras.toPlainText() else None),
            Passo("Revisão", self.w_rev, None, self._entrar_revisao),
        ]

    def _carregar_pastas(self) -> None:
        marcadas = {self.lista.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.lista.count())
                    if self.lista.item(i).checkState() == Qt.CheckState.Checked}
        extras = [self.lista.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.lista.count())
                  if not str(self.lista.item(i).data(Qt.ItemDataRole.UserRole)).startswith(str(self.cfg.pasta_htmls))]
        self.lista.clear()
        pastas = []
        if self.cfg.pasta_htmls.exists():
            pastas = sorted([p for p in self.cfg.pasta_htmls.iterdir() if p.is_dir()], key=lambda p: p.name.lower())
            if any(self.cfg.pasta_htmls.glob("*.html")):
                pastas.insert(0, self.cfg.pasta_htmls)
        for p in pastas + [Path(x) for x in extras]:
            self._item(p, str(p) in marcadas or not marcadas)

    def _item(self, p: Path, marcado: bool = True) -> None:
        n = sum(1 for _ in p.glob("*.html"))
        it = QListWidgetItem(f"{p.name if p != self.cfg.pasta_htmls else '(raiz)'}   ·   {n} currículos")
        it.setData(Qt.ItemDataRole.UserRole, str(p))
        it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        it.setCheckState(Qt.CheckState.Checked if marcado and n else Qt.CheckState.Unchecked)
        it.setToolTip(str(p))
        self.lista.addItem(it)

    def _adicionar(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Pasta com currículos HTML", str(Path.home()))
        if d:
            self._item(Path(d))

    def _marcar(self, sim: bool) -> None:
        for i in range(self.lista.count()):
            self.lista.item(i).setCheckState(Qt.CheckState.Checked if sim else Qt.CheckState.Unchecked)

    def _pastas(self) -> list[str]:
        return [self.lista.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.lista.count())
                if self.lista.item(i).checkState() == Qt.CheckState.Checked]

    def _validar(self) -> str:
        return "" if self._pastas() else "Marque pelo menos uma pasta com currículos."

    def _palavras(self) -> list[str]:
        return [l.strip() for l in self.t_palavras.toPlainText().splitlines() if l.strip()]

    def _entrar_revisao(self) -> None:
        limpar_layout(self.rev)
        pastas = self._pastas()
        n = sum(sum(1 for _ in Path(p).rglob("*.html")) for p in pastas)
        self.item_revisao(self.rev, "Planilha", self.e_titulo.text())
        self.item_revisao(self.rev, "Pastas", "\n".join(Path(p).name for p in pastas))
        self.item_revisao(self.rev, "Currículos", str(n))
        self.item_revisao(self.rev, "Palavras-chave", ", ".join(self._palavras()) or "nenhuma")
        self.item_revisao(self.rev, "Processos", f"{self.cfg.num_processos()} em paralelo")

    def iniciar(self) -> str:
        job = self.banco.criar(J.TIPO_PROCESSAR, self.e_titulo.text().strip() or "Compilação",
                               {"pastas": self._pastas(), "palavras": self._palavras()})
        return job.id


# ========================================================================== execução
class PaginaExecucao(Pagina):
    rolar = True   # em janelas baixas rola em vez de espremer os indicadores

    def __init__(self, janela) -> None:
        super().__init__(janela)
        self.job_id: str | None = None
        topo = QHBoxLayout()
        topo.setSpacing(tema.ESP_L)
        v = QVBoxLayout()
        v.setSpacing(6)
        self.l_tipo = rotulo("", "sobrelinha")
        self.l_titulo = rotulo("", "titulo")
        v.addWidget(self.l_tipo)
        v.addWidget(self.l_titulo)
        topo.addLayout(v, 1)
        self.pill = Pill("")
        topo.addWidget(self.pill, 0, Qt.AlignmentFlag.AlignVCenter)
        self.lay.addLayout(topo)
        self.lay.addSpacing(tema.ESP_XS)

        self.banner = Banner()
        self.lay.addWidget(self.banner)

        prog = Card()
        prog.lay.setSpacing(10)
        h = QHBoxLayout()
        h.setSpacing(10)
        self.spinner = Spinner()
        h.addWidget(self.spinner)
        self.l_etapa = rotulo("", None)
        self.l_etapa.setStyleSheet("font-weight: 600;")
        h.addWidget(self.l_etapa, 1)
        self.l_pct = QLabel("0%")
        self.l_pct.setStyleSheet(f"font-size: 16pt; font-weight: 750; color: {tema.VERDE};")
        h.addWidget(self.l_pct)
        prog.lay.addLayout(h)
        self.barra = ProgressoAnimado()
        prog.lay.addWidget(self.barra)
        self.l_detalhe = rotulo("", "suave")
        prog.lay.addWidget(self.l_detalhe)
        self.lay.addWidget(prog)

        g = GradeResponsiva(largura_min=140, max_colunas=6, espaco=tema.ESP_M, colunas_validas=(6, 3, 2))
        self.t_prog = Tile("Progresso", "0 / 0", "currículos", tema.VERDE)
        self.t_taxa = Tile("Velocidade", "—", "por minuto")
        self.t_eta = Tile("Tempo restante", "—", "estimativa", tema.AZUL)
        self.t_dec = Tile("Decorrido", "—")
        self.t_err = Tile("Erros", "0", "itens com falha")
        self.t_mem = Tile("Memória", "—", "deste processo", tema.ROXO)
        for t in (self.t_prog, self.t_taxa, self.t_eta, self.t_dec, self.t_err, self.t_mem):
            g.adicionar(t)
        self.lay.addWidget(g)
        self.lay.addSpacing(tema.ESP_XS)

        cab_log = QHBoxLayout()
        cab_log.setSpacing(tema.ESP_M)
        cab_log.addWidget(rotulo("Registro da execução", "secao"))
        cab_log.addStretch()
        self.filtro = QComboBox()
        self.filtro.addItems(["sem debug", "tudo", "avisos", "erros"])
        self.filtro.currentTextChanged.connect(lambda t: self.log.filtrar(t))
        self.c_rolar = QCheckBox("Rolar automaticamente")
        self.c_rolar.setChecked(True)
        self.c_rolar.toggled.connect(lambda v: setattr(self.log, "auto_rolar", v))
        cab_log.addWidget(self.c_rolar)
        cab_log.addWidget(self.filtro)
        self.lay.addLayout(cab_log)
        self.log = LogView()
        self.log.setMinimumHeight(150)
        self.lay.addWidget(self.log, 1)

        rod = QHBoxLayout()
        rod.setSpacing(tema.ESP_M)
        self.b_pausa = botao("Pausar", None, self._pausar, icone="pausa")
        self.b_parar = botao("Interromper", "perigo", self._parar, icone="parar")
        self.b_pasta = botao("Abrir pasta", None, self._abrir_pasta, icone="pasta")
        self.b_plan = botao("Abrir planilha", "primario", self._abrir_planilha, icone="arquivo")
        self.b_cont = botao("Continuar extração", "primario", self._continuar, icone="play")
        self.b_base = botao("Ver na base", None, self._ver_base, icone="base")
        rod.addWidget(self.b_pausa)
        rod.addWidget(self.b_parar)
        rod.addStretch()
        rod.addWidget(self.b_pasta)
        rod.addWidget(self.b_base)
        rod.addWidget(self.b_cont)
        rod.addWidget(self.b_plan)
        self.lay.addLayout(rod)
        self._ultimo = {}

    # ---- ligação com a thread
    def acompanhar(self, job_id: str, execucao) -> None:
        if self.job_id != job_id:
            self.log.clear()
            self.log._linhas.clear()
            self._ultimo = {}
        self.job_id = job_id
        s = execucao.sinais
        s.log.connect(self.log.adicionar)
        s.progresso.connect(self._progresso)
        s.etapa.connect(self._etapa)
        s.aguardando.connect(self._aguardando)
        self.banner.hide()
        self._estado(True)

    def mostrar_job(self, job_id: str) -> None:
        if self.janela.execucao_ativa() != job_id:
            if self.job_id != job_id:
                self.log.clear()
                self.log._linhas.clear()
                log = Path(self.banco.obter(job_id).pasta or "") / "extracao.log"
                if log.is_file():
                    for l in log.read_text(encoding="utf-8", errors="replace").splitlines()[-400:]:
                        partes = l.split("] ", 1)
                        if len(partes) == 2:
                            nivel, _, msg = partes[1].partition(" ")
                            self.log.adicionar(msg, nivel.lower())
            self.job_id = job_id
            self._estado(False)

    def _estado(self, rodando: bool) -> None:
        job = self.banco.obter(self.job_id) if self.job_id else None
        if not job:
            return
        self.l_tipo.setText(job.rotulo_tipo.upper())
        self.l_titulo.setText(job.titulo)
        pausado = self.janela.execucao and self.janela.execucao.controle.pausado
        if rodando:
            self.pill.definir("Pausada" if pausado else "Em andamento", tema.AMARELO if pausado else tema.VERDE,
                              pulsar=not pausado)
            self.spinner.iniciar() if not pausado else self.spinner.parar()
        else:
            self.pill.definir(job.rotulo_status, tema.COR_STATUS.get(job.status, tema.SUAVE))
            self.spinner.parar()
            self.l_etapa.setText(job.mensagem or job.rotulo_status)
            self.banner.hide()
            self._preencher_tiles({"feitos": job.feitos + job.erros, "total": job.total, "erros": job.erros})
        self.barra.ativo = rodando and not pausado
        self.b_pausa.setVisible(rodando)
        self.b_parar.setVisible(rodando)
        self.b_pausa.setText("Continuar" if pausado else "Pausar")
        self.b_pausa.setIcon(icones.icone("play" if pausado else "pausa", tema.TEXTO, tamanho=16))
        self.b_cont.setVisible(not rodando and job.tipo != J.TIPO_PROCESSAR and job.status != J.CONCLUIDO)
        self.b_plan.setVisible(bool(job.saida) and Path(job.saida).exists())
        self.b_base.setVisible(not rodando and bool(job.pasta) and Path(job.pasta).is_dir()
                               and any(Path(job.pasta).glob("*.html")))
        self.b_pasta.setEnabled(bool(job.pasta or job.saida))

    def _progresso(self, d: dict) -> None:
        self._ultimo = d
        self._preencher_tiles(d)
        if d.get("detalhe"):
            self.l_detalhe.setText(f"Agora: {d['detalhe']}")
        if self.banner.isVisible():
            self.banner.hide()

    def _preencher_tiles(self, d: dict) -> None:
        tot, feitos = d.get("total") or 0, d.get("feitos") or 0
        fr = feitos / tot if tot else 0
        self.barra.ir_para(fr)
        self.l_pct.setText(f"{fr:.0%}")
        self.t_prog.definir(f"{feitos:,} / {tot:,}".replace(",", "."))
        if "taxa" in d:
            self.t_taxa.definir(f"{d['taxa']:.1f}" if d["taxa"] < 10 else f"{d['taxa']:.0f}")
            self.t_eta.definir(d.get("eta", "—"))
            self.t_dec.definir(d.get("decorrido", "—"))
            self.t_mem.definir(f"{d.get('memoria', 0):.0f} MB")
        self.t_err.definir(str(d.get("erros", 0)), cor=tema.VERMELHO if d.get("erros") else tema.TEXTO)

    def _etapa(self, texto: str) -> None:
        self.l_etapa.setText(texto)

    def _aguardando(self, motivo: str) -> None:
        self.banner.mostrar(motivo + "  A extração continua sozinha assim que a verificação for concluída.")
        self.janela.alertar()

    def _pausar(self) -> None:
        ex = self.janela.execucao
        if not ex:
            return
        if ex.controle.pausado:
            ex.controle.continuar()
            self.log.adicionar("Continuando…", "info")
        else:
            ex.controle.pausar()
            self.log.adicionar("Pausado. A tarefa atual termina e a extração espera.", "aviso")
            self.janela.banco.atualizar(self.job_id, status=J.PAUSADO)
        self._estado(True)

    def _parar(self) -> None:
        if QMessageBox.question(self, "Interromper", "Interromper a extração? Dá para continuar depois de onde parou.") \
                == QMessageBox.StandardButton.Yes and self.janela.execucao:
            self.janela.execucao.controle.cancelar()
            self.l_etapa.setText("Interrompendo…")

    def _continuar(self) -> None:
        if self.job_id:
            self.janela.iniciar(self.job_id)

    def _abrir_pasta(self) -> None:
        job = self.banco.obter(self.job_id) if self.job_id else None
        if job:
            abrir_local(job.pasta or Path(job.saida).parent)

    def _abrir_planilha(self) -> None:
        job = self.banco.obter(self.job_id) if self.job_id else None
        if job and job.saida:
            abrir_local(job.saida)

    def _ver_base(self) -> None:
        job = self.banco.obter(self.job_id) if self.job_id else None
        if job and job.pasta:
            self.janela.abrir_base(Path(job.pasta).name)

    def terminou(self) -> None:
        self._estado(False)
        job = self.banco.obter(self.job_id) if self.job_id else None
        if job:
            self.log.adicionar(f"Extração {job.rotulo_status.lower()}." + (f" Planilha: {job.saida}" if job.saida else ""),
                               "ok" if job.status == J.CONCLUIDO else "aviso")


# ========================================================================= extrações
class PaginaExtracoes(Pagina):
    COLS = ["Extração", "Tipo", "Status", "Progresso", "Itens", "Atualizada", "Mensagem"]

    def __init__(self, janela) -> None:
        super().__init__(janela)
        self.cabecalho("Extrações", "Tudo o que já foi coletado ou processado. As interrompidas continuam de onde pararam.")
        barra = QHBoxLayout()
        barra.setSpacing(tema.ESP_S)
        self.l_sel = rotulo("Nenhuma selecionada", "suave")
        barra.addWidget(self.l_sel, 1)
        self.b_ver = botao("Detalhes", None, self._ver, icone="detalhe")
        self.b_abrir = botao("Abrir planilha", None, self._abrir_planilha, icone="arquivo")
        self.b_cont = botao("Continuar", "primario", self._continuar, icone="play")
        self.b_mais = QToolButton()
        self.b_mais.setIcon(icones.icone("mais", tema.TEXTO, tamanho=16))
        self.b_mais.setToolTip("Mais ações")
        self.b_mais.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.b_mais.setCursor(Qt.CursorShape.PointingHandCursor)
        self.b_mais.setStyleSheet(f"QToolButton {{ background: {tema.SUPERFICIE_2}; border: 1px solid {tema.BORDA};"
                                  "border-radius: 9px; padding: 8px 10px; } QToolButton::menu-indicator { image: none; }")
        menu = QMenu(self)
        self.a_plan = menu.addAction(icones.icone("refazer", tema.TEXTO), "Gerar planilha de novo", self._regerar)
        self.a_base = menu.addAction(icones.icone("base", tema.TEXTO), "Ver currículos na base", self._ver_base)
        self.a_pasta = menu.addAction(icones.icone("pasta", tema.TEXTO), "Abrir pasta dos currículos", self._abrir_pasta)
        menu.addSeparator()
        self.a_del = menu.addAction(icones.icone("lixo", tema.VERMELHO), "Remover do histórico", self._remover)
        self.b_mais.setMenu(menu)
        for b in (self.b_ver, self.b_abrir, self.b_cont, self.b_mais):
            barra.addWidget(b)
        self.lay.addLayout(barra)
        self.tab = QTableWidget(0, len(self.COLS))
        self.tab.setHorizontalHeaderLabels(self.COLS)
        self.tab.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tab.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tab.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tab.verticalHeader().setVisible(False)
        self.tab.verticalHeader().setDefaultSectionSize(54)
        self.tab.setShowGrid(False)
        self.tab.setWordWrap(False)
        self.tab.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        hh = self.tab.horizontalHeader()
        hh.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        hh.setHighlightSections(False)
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        for c, w in ((1, 140), (2, 150), (3, 150), (4, 90), (5, 150)):
            self.tab.setColumnWidth(c, w)
        self.tab.itemSelectionChanged.connect(self._botoes)
        self.tab.doubleClicked.connect(lambda *_: self._ver())
        self.lay.addWidget(self.tab, 1)
        self.jobs: list[J.Job] = []

    def ao_mostrar(self) -> None:
        self.jobs = self.banco.listar(500)
        self.tab.setRowCount(len(self.jobs))
        ativo = self.janela.execucao_ativa()
        for i, j in enumerate(self.jobs):
            status = "Em andamento" if j.id == ativo else j.rotulo_status
            cor = tema.VERDE if j.id == ativo else tema.COR_STATUS.get(j.status, tema.SUAVE)
            itens = [j.titulo, j.rotulo_tipo, "", "",
                     f"{j.feitos:,}/{j.total:,}".replace(",", ".") if j.total else "—", quando(j.atualizado), j.mensagem]
            for c, t in enumerate(itens):
                it = QTableWidgetItem(t)
                it.setToolTip(j.pasta if c == 0 and j.pasta else t)
                if c == 0:
                    f = it.font()
                    f.setWeight(f.Weight.DemiBold)
                    it.setFont(f)
                elif c != 4:
                    it.setForeground(QColor(tema.SUAVE))
                self.tab.setItem(i, c, it)
            pill = Pill()
            pill.definir(status, cor, pulsar=j.id == ativo)
            self.tab.setCellWidget(i, 2, caixa_v(None, caixa_h(pill, None), None, espaco=0, margens=(10, 0, 4, 0)))
            pb = QProgressBar()
            pb.setRange(0, 1000)
            pb.setValue(int(j.fracao * 1000))
            pb.setFixedHeight(6)
            self.tab.setCellWidget(i, 3, caixa_v(None, pb, None, margens=(12, 0, 12, 0)))
        self._colunas()
        self._botoes()

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self._colunas()

    def _colunas(self) -> None:
        """Em janelas estreitas some a coluna Mensagem (o texto fica na dica) e depois a Tipo."""
        w = self.tab.viewport().width()
        self.tab.setColumnHidden(6, w < 1000)
        self.tab.setColumnHidden(1, w < 820)

    def _sel(self) -> J.Job | None:
        r = self.tab.currentRow()
        return self.jobs[r] if 0 <= r < len(self.jobs) and self.tab.selectedItems() else None

    def _botoes(self) -> None:
        j = self._sel()
        ativo = self.janela.execucao_ativa()
        tem = j is not None
        self.l_sel.setText(f"Selecionada: {j.titulo}" if tem else
                           f"{len(self.jobs)} extrações · selecione uma linha para agir")
        self.b_ver.setEnabled(tem)
        self.b_cont.setEnabled(tem and j.tipo != J.TIPO_PROCESSAR and j.status != J.CONCLUIDO and ativo is None)
        self.a_plan.setEnabled(tem and ativo is None and j.tipo != J.TIPO_PROCESSAR)
        self.b_abrir.setEnabled(tem and bool(j.saida) and Path(j.saida).exists())
        self.a_pasta.setEnabled(tem and bool(j.pasta))
        self.a_base.setEnabled(tem and bool(j.pasta))
        self.a_del.setEnabled(tem and j.id != ativo)
        self.b_mais.setEnabled(tem)

    def _ver(self) -> None:
        j = self._sel()
        if j:
            self.janela.mostrar_execucao(j.id)

    def _continuar(self) -> None:
        j = self._sel()
        if j:
            self.janela.iniciar(j.id)

    def _regerar(self) -> None:
        j = self._sel()
        if j:
            self.janela.iniciar(j.id, somente_planilha=True)

    def _abrir_planilha(self) -> None:
        j = self._sel()
        if j and j.saida:
            abrir_local(j.saida)

    def _abrir_pasta(self) -> None:
        j = self._sel()
        if j and j.pasta:
            abrir_local(j.pasta)

    def _ver_base(self) -> None:
        j = self._sel()
        if j and j.pasta:
            self.janela.abrir_base(Path(j.pasta).name)

    def _remover(self) -> None:
        j = self._sel()
        if j and QMessageBox.question(
                self, "Remover", f"Remover \"{j.titulo}\" do histórico?\n\nOs currículos baixados e as planilhas "
                                 "continuam na pasta de trabalho.") == QMessageBox.StandardButton.Yes:
            self.banco.excluir(j.id)
            self.ao_mostrar()


# ======================================================================= configurações
class PaginaConfig(Pagina):
    def __init__(self, janela) -> None:
        super().__init__(janela)
        self.cabecalho("Configurações", "Valem para as próximas extrações e ficam salvas neste computador.")
        corpo = QWidget()
        v = QVBoxLayout(corpo)
        v.setContentsMargins(0, 0, 6, tema.ESP_S)
        v.setSpacing(tema.ESP_L)

        g1 = CardForm("Pasta de trabalho", "Currículos (htmls), planilhas, histórico de extrações e o perfil do Chrome.")
        self.e_pasta = QLineEdit()
        caixa_pasta = caixa_h(self.e_pasta, botao("Escolher…", None, self._escolher_pasta, icone="pasta"), espaco=tema.ESP_S)
        g1.campo("Local", caixa_pasta, largura=720)
        v.addWidget(g1)

        g2 = CardForm("Coleta no CNPq", "Ritmo e comportamento do Chrome durante a coleta.")
        self.s_atraso = QDoubleSpinBox(); self.s_atraso.setRange(1, 120); self.s_atraso.setSuffix(" s")
        self.s_atraso_b = QDoubleSpinBox(); self.s_atraso_b.setRange(0.5, 60); self.s_atraso_b.setSuffix(" s")
        self.s_timeout = QSpinBox(); self.s_timeout.setRange(10, 300); self.s_timeout.setSuffix(" s")
        self.c_pag = QComboBox(); self.c_pag.addItems(["10", "20", "50", "100"])
        self.s_bloq = QSpinBox(); self.s_bloq.setRange(30, 3600); self.s_bloq.setSuffix(" s")
        self.c_som = QCheckBox("Tocar alerta quando precisar de você (captcha)")
        self.c_perfil = QCheckBox("Manter o perfil do Chrome entre execuções")
        g2.campo("Intervalo entre currículos", self.s_atraso, "Com variação aleatória de ±30%.", 180)
        g2.campo("Intervalo entre buscas de nome", self.s_atraso_b, "", 180)
        g2.campo("Tempo máximo por página", self.s_timeout, "Depois disso a página conta como falha.", 180)
        g2.campo("Resultados por página", self.c_pag, "Menos páginas para percorrer com 100.", 180)
        g2.campo("Espera se o site bloquear", self.s_bloq, "Pausa antes de recarregar quando a listagem some.", 180)
        g2.campo("Avisos", self.c_som)
        g2.campo("Perfil do Chrome", self.c_perfil, "Guarda cookies: o CNPq pede menos verificações.")
        v.addWidget(g2)

        g4 = CardForm("Busca por nomes", "Como os homônimos são desempatados.")
        self.s_nota = QSpinBox(); self.s_nota.setRange(10, 100); self.s_nota.setSuffix(" %")
        self.s_margem = QSpinBox(); self.s_margem.setRange(0, 80); self.s_margem.setSuffix(" %")
        self.s_cvs = QSpinBox(); self.s_cvs.setRange(0, 20)
        self.s_sim = QSpinBox(); self.s_sim.setRange(50, 100); self.s_sim.setSuffix(" %")
        g4.campo("Confiança mínima", self.s_nota, "Nota mínima para aceitar um perfil.", 180)
        g4.campo("Vantagem sobre o 2º", self.s_margem, "Diferença mínima entre o 1º e o 2º colocados.", 180)
        g4.campo("Currículos completos por empate", self.s_cvs, "0 = decidir só pelo resumo da busca.", 180)
        g4.campo("Semelhança mínima do nome", self.s_sim, "Abaixo disso o perfil nem entra na disputa.", 180)
        v.addWidget(g4)

        g3 = CardForm("Processamento e planilhas")
        self.s_proc = QSpinBox(); self.s_proc.setRange(0, 64)
        self.s_proc.setSpecialValueText(f"automático ({os.cpu_count()} núcleos)")
        self.c_tsv = QCheckBox("Gerar também o .txt (TSV) completo")
        self.c_abrir = QCheckBox("Mostrar botão para abrir a planilha ao terminar")
        g3.campo("Processos em paralelo", self.s_proc, "", 240)
        g3.campo("Arquivos", self.c_tsv, "O .txt não tem o limite de 32.767 caracteres por célula do Excel.")
        g3.campo("Ao terminar", self.c_abrir)
        self.t_pal = QPlainTextEdit(); self.t_pal.setMinimumHeight(160)
        self.e_siglas = QLineEdit()
        g3.campo("Palavras-chave", self.t_pal, "Uma por linha. Contadas em cada currículo, sem acento e sem "
                                               "diferenciar maiúsculas.")
        g3.campo("Siglas", self.e_siglas, "Separadas por vírgula. Só contam como palavra inteira (ex.: cbd, thc).")
        v.addWidget(g3)

        g6 = CardForm("Interface")
        self.c_intro = QCheckBox("Mostrar a animação de abertura")
        g6.campo("Abertura", self.c_intro)
        v.addWidget(g6)
        v.addStretch()
        self.lay.addWidget(rolavel(corpo), 1)

        self.lay.addWidget(linha())
        rod = QHBoxLayout()
        rod.setSpacing(tema.ESP_M)
        self.l_ok = rotulo("", None)
        self.l_ok.setStyleSheet(f"color: {tema.VERDE}; font-weight: 600;")
        rod.addWidget(self.l_ok, 1)
        rod.addWidget(botao("Restaurar padrões", None, self._padroes, icone="refazer"))
        rod.addWidget(botao("Salvar", "primario", self._salvar))
        self.lay.addLayout(rod)

    def ao_mostrar(self) -> None:
        self._preencher(self.cfg)

    def _preencher(self, c: Config) -> None:
        self.e_pasta.setText(c.pasta_trabalho)
        self.s_atraso.setValue(c.atraso_entre_curriculos)
        self.s_atraso_b.setValue(c.atraso_entre_buscas)
        self.s_timeout.setValue(c.timeout_pagina)
        self.c_pag.setCurrentText(str(c.resultados_por_pagina))
        self.s_bloq.setValue(c.espera_bloqueio)
        self.c_som.setChecked(c.alerta_sonoro)
        self.c_perfil.setChecked(c.chrome_perfil_persistente)
        self.s_proc.setValue(c.processos)
        self.c_tsv.setChecked(c.gerar_tsv)
        self.c_abrir.setChecked(c.abrir_planilha_ao_terminar)
        self.s_nota.setValue(int(c.nota_minima * 100))
        self.s_margem.setValue(int(c.margem_desempate * 100))
        self.s_cvs.setValue(c.max_candidatos_cv)
        self.s_sim.setValue(c.similaridade_nome)
        self.t_pal.setPlainText("\n".join(c.palavras_chave))
        self.e_siglas.setText(", ".join(c.siglas_palavra_inteira))
        self.c_intro.setChecked(c.mostrar_intro)
        self.l_ok.setText("")

    def _escolher_pasta(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Pasta de trabalho", self.e_pasta.text())
        if d:
            self.e_pasta.setText(d)

    def _padroes(self) -> None:
        self._preencher(Config())
        self.l_ok.setText("Padrões carregados. Clique em Salvar para aplicar.")

    def _salvar(self) -> None:
        if self.janela.execucao_ativa() and self.e_pasta.text() != self.cfg.pasta_trabalho:
            self.l_ok.setText("Espere a extração terminar para trocar a pasta de trabalho.")
            return
        c = self.cfg
        mudou_pasta = self.e_pasta.text() != c.pasta_trabalho
        c.pasta_trabalho = self.e_pasta.text().strip() or c.pasta_trabalho
        c.atraso_entre_curriculos = self.s_atraso.value()
        c.atraso_entre_buscas = self.s_atraso_b.value()
        c.timeout_pagina = self.s_timeout.value()
        c.resultados_por_pagina = int(self.c_pag.currentText())
        c.espera_bloqueio = self.s_bloq.value()
        c.alerta_sonoro = self.c_som.isChecked()
        c.chrome_perfil_persistente = self.c_perfil.isChecked()
        c.processos = self.s_proc.value()
        c.gerar_tsv = self.c_tsv.isChecked()
        c.abrir_planilha_ao_terminar = self.c_abrir.isChecked()
        c.nota_minima = self.s_nota.value() / 100
        c.margem_desempate = self.s_margem.value() / 100
        c.max_candidatos_cv = self.s_cvs.value()
        c.similaridade_nome = self.s_sim.value()
        c.palavras_chave = [l.strip() for l in self.t_pal.toPlainText().splitlines() if l.strip()] or list(PALAVRAS_CHAVE_PADRAO)
        c.siglas_palavra_inteira = [s.strip() for s in self.e_siglas.text().split(",") if s.strip()]
        c.mostrar_intro = self.c_intro.isChecked()
        c.salvar()
        if mudou_pasta:
            self.janela.trocar_pasta()
        self.l_ok.setText("✔ Configurações salvas.")
        QTimer.singleShot(3500, lambda: self.l_ok.setText(""))

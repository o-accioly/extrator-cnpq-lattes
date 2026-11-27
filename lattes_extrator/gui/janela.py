"""Janela principal: barra lateral + páginas, e o controle da extração em andamento."""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QCloseEvent, QGuiApplication
from PySide6.QtWidgets import (QApplication, QButtonGroup, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QMainWindow,
                               QMessageBox, QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from .. import NOME_APP, __version__
from .. import diagnostico as D
from .. import jobs as J
from ..config import Config
from . import icones, tema
from .paginas import (AssistenteBusca, AssistenteNomes, AssistenteProcessar, PaginaConfig, PaginaExecucao,
                      PaginaExtracoes, PaginaInicio)
from .pagina_base import PaginaBase, PaginaPerfil
from .diagnostico import DialogoDiagnostico, TrabalhoDiagnostico, texto_bloqueio
from .workers import Execucao

FUNCAO_DO_TIPO = {J.TIPO_BUSCA: D.COLETA, J.TIPO_NOMES: D.NOMES, J.TIPO_PROCESSAR: D.PLANILHA}


class JanelaPrincipal(QMainWindow):
    def __init__(self, cfg: Config) -> None:
        super().__init__()
        self.cfg = cfg
        self.aviso_pasta = self.cfg.garantir_pastas_ou_padrao()
        self.banco = J.Banco(cfg.banco)
        self.execucao: Execucao | None = None
        self.diag: D.Resultado | None = None
        self._trabalho_diag: TrabalhoDiagnostico | None = None
        self.setWindowTitle(NOME_APP)
        self.setMinimumSize(960, 640)
        tela = QGuiApplication.primaryScreen()
        if tela:
            g = tela.availableGeometry()
            self.resize(min(1440, int(g.width() * 0.9)), min(920, int(g.height() * 0.9)))

        central = QWidget()
        h = QHBoxLayout(central)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        h.addWidget(self._barra_lateral())
        self.pilha = QStackedWidget()
        h.addWidget(self.pilha, 1)
        self.setCentralWidget(central)

        self.paginas = {
            "inicio": PaginaInicio(self),
            "busca": AssistenteBusca(self),
            "nomes": AssistenteNomes(self),
            "processar": AssistenteProcessar(self),
            "execucao": PaginaExecucao(self),
            "extracoes": PaginaExtracoes(self),
            "config": PaginaConfig(self),
            "base": PaginaBase(self),
            "perfil": PaginaPerfil(self),
        }
        for p in self.paginas.values():
            self.pilha.addWidget(p)
        self.ir("inicio")
        QTimer.singleShot(0, self.verificar_ambiente)

    # ------------------------------------------------------- verificação do ambiente
    def verificar_ambiente(self) -> None:
        """Roda todas as checagens em segundo plano (o teste de rede leva alguns segundos)."""
        if self._trabalho_diag and self._trabalho_diag.isRunning():
            return
        self._trabalho_diag = TrabalhoDiagnostico(self.cfg)
        self._trabalho_diag.pronto.connect(self._ambiente_verificado)
        self._trabalho_diag.start()

    def _ambiente_verificado(self, res: D.Resultado) -> None:
        self.diag = res
        inicio: PaginaInicio = self.paginas["inicio"]
        inicio.mostrar_ambiente(res, self.aviso_pasta)
        self.paginas["config"].mostrar_ambiente(res)

    def ver_diagnostico(self) -> None:
        dlg = DialogoDiagnostico(self.cfg, self.diag, self)
        dlg.atualizado.connect(self._ambiente_verificado)
        dlg.exec()

    def _bloqueios(self, funcao: str) -> list[D.Checagem]:
        res = self.diag
        if res is None:   # ainda verificando: checagem local rápida, sem rede
            res = D.executar(self.cfg, rede=False)
        return res.bloqueia(funcao)

    # ------------------------------------------------------------ barra lateral
    def _barra_lateral(self) -> QWidget:
        lado = QWidget()
        lado.setObjectName("Sidebar")
        lado.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.lado = lado
        lado.setFixedWidth(232)
        v = QVBoxLayout(lado)
        v.setContentsMargins(12, 22, 12, 16)
        v.setSpacing(2)
        self.logo = QLabel()
        self.logo.setContentsMargins(10, 0, 0, 14)
        v.addWidget(self.logo)
        self.nav = QButtonGroup(self)
        self.nav.setExclusive(True)
        self.botoes: dict[str, QPushButton] = {}
        self.textos: dict[str, str] = {}
        self.grupos: list[QLabel] = []
        itens = [("inicio", "inicio", "Início", None),
                 ("busca", "busca", "Coletar pela busca", "FUNÇÕES"),
                 ("nomes", "nomes", "Buscar por nomes", None),
                 ("processar", "planilha", "Gerar planilha", None),
                 ("base", "base", "Base de currículos", "DADOS"),
                 ("execucao", "execucao", "Execução", "ACOMPANHAR"),
                 ("extracoes", "extracoes", "Extrações", None)]
        for chave, ic, texto, grupo in itens:
            if grupo:
                g = QLabel(grupo)
                g.setProperty("papel", "grupo")
                self.grupos.append(g)
                v.addWidget(g)
            v.addWidget(self._botao_nav(chave, ic, texto))
        v.addStretch()
        self.l_status = QLabel("")
        self.l_status.setWordWrap(True)
        self.l_status.setStyleSheet(f"color:{tema.VERDE}; font-size:8.5pt; padding: 8px 10px; "
                                    f"background:{tema.mistura(tema.VERDE, 0.08)}; border-radius: 8px;")
        self.l_status.hide()
        v.addWidget(self.l_status)
        v.addSpacing(tema.ESP_S)
        v.addWidget(self._botao_nav("config", "config", "Configurações"))
        self._compacto = None
        self._modo_compacto(False)
        return lado

    def _botao_nav(self, chave: str, ic: str, texto: str) -> QPushButton:
        b = QPushButton(texto)
        b.setCheckable(True)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setIcon(icones.icone(ic, tema.SUAVE, tema.VERDE))
        b.setIconSize(icones.TAMANHO)
        b.setToolTip(texto)
        b.clicked.connect(lambda _c=False, k=chave: self.ir(k))
        self.nav.addButton(b)
        self.botoes[chave] = b
        self.textos[chave] = texto
        return b

    def _modo_compacto(self, sim: bool) -> None:
        """Janelas estreitas: barra lateral só com ícones (72 px)."""
        if sim == self._compacto:
            return
        self._compacto = sim
        self.lado.setFixedWidth(72 if sim else 232)
        for chave, b in self.botoes.items():
            b.setText("" if sim else "   " + self.textos[chave])
            b.setProperty("compacto", "true" if sim else "false")
            b.style().unpolish(b)
            b.style().polish(b)
        for g in self.grupos:
            g.setVisible(not sim)
        if sim:
            self.logo.setText(f"<span style='color:{tema.VERDE}; font-family:monospace; font-size:15pt; font-weight:800'>▌L</span>")
            self.logo.setContentsMargins(14, 0, 0, 14)
        else:
            self.logo.setText(f"<span style='color:{tema.VERDE}; font-family:monospace; font-size:15pt; font-weight:800'>▌LATTES</span>"
                              f"<br><span style='color:{tema.SUAVE}; font-size:8.5pt'>Extrator CNPq · v{__version__}</span>")
            self.logo.setContentsMargins(10, 0, 0, 14)

    def resizeEvent(self, e) -> None:
        self._modo_compacto(self.width() < 1100)
        super().resizeEvent(e)

    # --------------------------------------------------------------- navegação
    def ir(self, chave: str) -> None:
        pagina = self.paginas[chave]
        if self.pilha.currentWidget() is not pagina:
            self.pilha.setCurrentWidget(pagina)
            self._animar(pagina)
        if chave in self.botoes:
            self.botoes[chave].setChecked(True)
        pagina.ao_mostrar()

    def _animar(self, w: QWidget) -> None:
        ef = QGraphicsOpacityEffect(w)
        w.setGraphicsEffect(ef)
        an = QPropertyAnimation(ef, b"opacity", w)
        an.setDuration(220)
        an.setStartValue(0.0)
        an.setEndValue(1.0)
        an.setEasingCurve(QEasingCurve.Type.OutCubic)
        an.finished.connect(lambda: w.setGraphicsEffect(None))
        an.start()

    def abrir_assistente(self, chave: str) -> None:
        self.paginas[chave].reiniciar()
        self.ir(chave)

    def abrir_perfil(self, arquivo: str, termo: str = "") -> None:
        pag: PaginaPerfil = self.paginas["perfil"]
        try:
            pag.carregar(arquivo, termo)
        except OSError as e:
            QMessageBox.warning(self, "Perfil", f"Não foi possível abrir o arquivo:\n{e}")
            return
        self.ir("perfil")
        self.botoes["base"].setChecked(True)

    def abrir_base(self, pasta: str = "") -> None:
        self.ir("base")
        if pasta:
            self.paginas["base"].filtrar_pasta(pasta)

    def mostrar_execucao(self, job_id: str) -> None:
        pag: PaginaExecucao = self.paginas["execucao"]
        if self.execucao_ativa() == job_id:
            pag.job_id = job_id
            pag._estado(True)
        else:
            pag.mostrar_job(job_id)
        self.ir("execucao")

    # ------------------------------------------------------------- execução
    def execucao_ativa(self) -> str | None:
        if self.execucao and self.execucao.isRunning():
            return self.execucao.job_id
        return None

    def iniciar(self, job_id: str, somente_planilha: bool = False) -> None:
        if self.execucao_ativa():
            if self.execucao_ativa() != job_id:
                QMessageBox.information(self, "Extração em andamento",
                                        "Já existe uma extração rodando. Espere terminar ou interrompa para iniciar outra.")
            self.mostrar_execucao(self.execucao_ativa())
            return
        job = self.banco.obter(job_id)
        funcao = D.PLANILHA if somente_planilha else FUNCAO_DO_TIPO.get(job.tipo if job else "", D.PLANILHA)
        problemas = self._bloqueios(funcao)
        if problemas:
            caixa = QMessageBox(QMessageBox.Icon.Critical, "Não dá para iniciar", texto_bloqueio(problemas, funcao),
                                QMessageBox.StandardButton.Close, self)
            detalhes = caixa.addButton("Ver verificação completa", QMessageBox.ButtonRole.ActionRole)
            caixa.exec()
            if caixa.clickedButton() is detalhes:
                self.ver_diagnostico()
            return
        self.execucao = Execucao(job_id, self.banco, self.cfg, somente_planilha)
        pag: PaginaExecucao = self.paginas["execucao"]
        pag.acompanhar(job_id, self.execucao)
        self.execucao.sinais.terminou.connect(self._terminou)
        self.execucao.sinais.progresso.connect(self._status_lateral)
        self.execucao.start()
        self.botoes["execucao"].setStyleSheet(f"color: {tema.VERDE};")
        self.ir("execucao")

    def _status_lateral(self, d: dict) -> None:
        tot = d.get("total") or 0
        if self._compacto:
            self.l_status.setText(f"{(d.get('feitos', 0) / tot):.0%}" if tot else "…")
        else:
            self.l_status.setText(f"● Extraindo {d.get('feitos', 0)}/{tot}" + (f" · {d.get('eta')}" if tot else ""))
        self.l_status.show()

    def _terminou(self, job_id: str) -> None:
        self.botoes["execucao"].setStyleSheet("")
        self.l_status.setText("")
        self.l_status.hide()
        self.paginas["execucao"].terminou()
        atual = self.pilha.currentWidget()
        if atual is not self.paginas["execucao"] and hasattr(atual, "ao_mostrar"):
            atual.ao_mostrar()
        QApplication.alert(self)

    def alertar(self) -> None:
        QApplication.alert(self, 0)
        QApplication.beep()

    def trocar_pasta(self) -> None:
        self.aviso_pasta = self.cfg.garantir_pastas_ou_padrao()
        self.banco.fechar()
        self.banco = J.Banco(self.cfg.banco)
        self.verificar_ambiente()

    def closeEvent(self, e: QCloseEvent) -> None:
        if self.execucao_ativa():
            r = QMessageBox.question(self, "Sair", "Há uma extração em andamento. Interromper e sair?\n"
                                                  "Dá para continuar depois de onde parou.")
            if r != QMessageBox.StandardButton.Yes:
                e.ignore()
                return
            self.execucao.controle.cancelar()
            self.execucao.wait(15000)
        self.banco.fechar()
        if self._trabalho_diag and self._trabalho_diag.isRunning():
            self._trabalho_diag.wait(10000)
        base = self.paginas["base"]
        if base.indexador and base.indexador.isRunning():
            base.indexador.wait(5000)
        e.accept()

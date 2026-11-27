"""Verificação do ambiente na interface: roda ao abrir (em segundo plano), mostra o resultado
num diálogo e impede iniciar uma função que vai falhar por falta de algo."""
from __future__ import annotations

import json
import sys

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (QApplication, QDialog, QFrame, QHBoxLayout, QScrollArea, QVBoxLayout,
                               QWidget)

from .. import diagnostico as D
from ..config import Config, pasta_dados_usuario
from . import tema
from .widgets import Pill, Spinner, botao, linha, rotulo

COR = {D.OK: tema.VERDE, D.AVISO: tema.AMARELO, D.ERRO: tema.VERMELHO}
ROTULO = {D.OK: "ok", D.AVISO: "atenção", D.ERRO: "problema"}


def checar_visualizador() -> D.Checagem:
    """O QtWebEngine é carregado em ``preparar_webengine`` antes do QApplication; aqui só
    confere se deu certo. Sem ele o currículo original abre no modo simplificado."""
    nome = "Visualizador do currículo original (QtWebEngine)"
    if "PySide6.QtWebEngineWidgets" in sys.modules:
        return D.Checagem(nome, D.OK, "", "", (D.BASE,))
    return D.Checagem(nome, D.AVISO, "Motor web indisponível; o currículo abre no modo simplificado.",
                      "Os dados continuam completos; só a aparência fica diferente da do site do CNPq.", (D.BASE,))


def salvar_relatorio(res: D.Resultado) -> None:
    """Guarda o último resultado em diagnostico.json (pasta de configuração), para suporte."""
    try:
        arq = pasta_dados_usuario() / "diagnostico.json"
        arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_text(json.dumps([c.como_dict() for c in res.checagens], ensure_ascii=False, indent=2),
                       encoding="utf-8")
    except OSError:
        pass


class TrabalhoDiagnostico(QThread):
    pronto = Signal(object)          # D.Resultado

    def __init__(self, cfg: Config, rede: bool = True) -> None:
        super().__init__()
        self.cfg = cfg
        self.rede = rede

    def run(self) -> None:
        res = D.executar(self.cfg, rede=self.rede, extras=[checar_visualizador])
        salvar_relatorio(res)
        self.pronto.emit(res)


class _Linha(QFrame):
    def __init__(self, c: D.Checagem) -> None:
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(0, tema.ESP_S, 0, tema.ESP_S)
        h.setSpacing(tema.ESP_M)
        pill = Pill(ROTULO[c.status], COR[c.status])
        pill.setFixedWidth(104)
        h.addWidget(pill, 0, Qt.AlignmentFlag.AlignTop)
        v = QVBoxLayout()
        v.setSpacing(2)
        v.addWidget(rotulo(c.nome, "secao"))
        if c.detalhe:
            v.addWidget(rotulo(c.detalhe, "suave", quebra=True))
        if c.dica and not c.ok:
            d = rotulo(c.dica, None, quebra=True)
            d.setStyleSheet(f"color: {COR[c.status]};")
            v.addWidget(d)
        if c.afeta and not c.ok:
            v.addWidget(rotulo("Afeta: " + ", ".join(c.afeta), "suave", quebra=True))
        h.addLayout(v, 1)


class DialogoDiagnostico(QDialog):
    """Lista cada verificação com status, detalhe e o que fazer."""
    atualizado = Signal(object)

    def __init__(self, cfg: Config, res: D.Resultado | None = None, parent=None) -> None:
        super().__init__(parent)
        self.cfg = cfg
        self.res = res
        self.trabalho: TrabalhoDiagnostico | None = None
        self.setWindowTitle("Verificação do ambiente")
        self.setModal(True)
        self.setMinimumSize(640, 520)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(tema.ESP_XL, tema.ESP_XL, tema.ESP_XL, tema.ESP_L)
        lay.setSpacing(tema.ESP_M)
        lay.addWidget(rotulo("Verificação do ambiente", "titulo"))
        self.l_resumo = rotulo("", "subtitulo", quebra=True)
        lay.addWidget(self.l_resumo)
        self.spinner = Spinner()
        self.spinner.hide()
        lay.addWidget(self.spinner)
        self.corpo = QVBoxLayout()
        self.corpo.setSpacing(0)
        miolo = QWidget()
        miolo.setLayout(self.corpo)
        rol = QScrollArea()
        rol.setWidgetResizable(True)
        rol.setFrameShape(QScrollArea.Shape.NoFrame)
        rol.setWidget(miolo)
        lay.addWidget(rol, 1)
        lay.addWidget(linha())
        rod = QHBoxLayout()
        rod.setSpacing(tema.ESP_M)
        self.b_copiar = botao("Copiar relatório", None, self._copiar, icone="arquivo")
        rod.addWidget(self.b_copiar)
        rod.addStretch()
        self.b_refazer = botao("Verificar de novo", None, self.verificar, icone="refazer")
        rod.addWidget(self.b_refazer)
        rod.addWidget(botao("Fechar", "primario", self.accept))
        lay.addLayout(rod)
        if res is None:
            self.verificar()
        else:
            self._mostrar(res)

    def verificar(self) -> None:
        if self.trabalho and self.trabalho.isRunning():
            return
        self.b_refazer.setEnabled(False)
        self.spinner.iniciar()
        self.l_resumo.setText("Verificando… (o teste de acesso ao CNPq leva alguns segundos)")
        self.trabalho = TrabalhoDiagnostico(self.cfg)
        self.trabalho.pronto.connect(self._mostrar)
        self.trabalho.start()

    def _mostrar(self, res: D.Resultado) -> None:
        self.res = res
        self.spinner.parar()
        self.b_refazer.setEnabled(True)
        self.l_resumo.setText(res.resumo())
        while self.corpo.count():
            w = self.corpo.takeAt(0).widget()
            if w:
                w.setParent(None)
        ordem = {D.ERRO: 0, D.AVISO: 1, D.OK: 2}
        itens = sorted(res.checagens, key=lambda c: ordem[c.status])
        for i, c in enumerate(itens):
            self.corpo.addWidget(_Linha(c))
            if i < len(itens) - 1:
                self.corpo.addWidget(linha())
        self.corpo.addStretch()
        self.atualizado.emit(res)

    def _copiar(self) -> None:
        if self.res:
            from .. import NOME_APP, __version__
            QApplication.clipboard().setText(f"{NOME_APP} v{__version__} ({sys.platform})\n" + D.texto(self.res))
            self.b_copiar.setText("Copiado ✔")

    def done(self, r: int) -> None:
        if self.trabalho and self.trabalho.isRunning():
            self.trabalho.wait(10000)
        super().done(r)


def texto_bloqueio(problemas: list[D.Checagem], funcao: str) -> str:
    itens = "\n".join(f"• {c.nome}: {c.detalhe}\n   {c.dica}" for c in problemas)
    return f"“{funcao}” não vai funcionar neste computador agora:\n\n{itens}"



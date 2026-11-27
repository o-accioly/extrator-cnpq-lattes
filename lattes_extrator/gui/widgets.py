"""Componentes visuais reutilizados pelas páginas."""
from __future__ import annotations

import datetime as dt
import html

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen, QTextCursor
from PySide6.QtWidgets import (QFrame, QGraphicsDropShadowEffect, QGridLayout, QHBoxLayout, QLabel,
                               QProgressBar, QPushButton, QSizePolicy, QTextEdit, QVBoxLayout, QWidget)

from . import icones, tema


def rotulo(texto: str, papel: str | None = None, quebra: bool = False) -> QLabel:
    l = QLabel(texto)
    if papel:
        l.setProperty("papel", papel)
    l.setWordWrap(quebra)
    l.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse if quebra else Qt.TextInteractionFlag.NoTextInteraction)
    return l


def botao(texto: str, papel: str | None = None, ao_clicar=None, dica: str = "", icone: str | None = None) -> QPushButton:
    b = QPushButton(texto)
    if papel:
        b.setProperty("papel", papel)
    if icone:
        cor = {"primario": "#04130C", "perigo": tema.VERMELHO, "link": tema.AZUL}.get(papel or "", tema.TEXTO)
        b.setIcon(icones.icone(icone, cor, tamanho=16))
        b.setIconSize(icones.QSize(16, 16))
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if dica:
        b.setToolTip(dica)
    if ao_clicar:
        b.clicked.connect(ao_clicar)
    return b


def linha() -> QFrame:
    f = QFrame()
    f.setProperty("papel", "linha")
    return f


def sombra(w: QWidget, raio: int = 28, alfa: int = 110) -> None:
    ef = QGraphicsDropShadowEffect(w)
    ef.setBlurRadius(raio)
    ef.setOffset(0, 6)
    ef.setColor(QColor(0, 0, 0, alfa))
    w.setGraphicsEffect(ef)


class Card(QFrame):
    clicado = Signal()

    def __init__(self, clicavel: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("papel", "card")
        self.setProperty("clicavel", "true" if clicavel else "false")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, clicavel)
        if clicavel:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(tema.ESP_XL, 20, tema.ESP_XL, 22)
        self.lay.setSpacing(tema.ESP_M)
        self._clicavel = clicavel

    def titulo(self, texto: str, sub: str = "", direita: QWidget | None = None) -> None:
        """Título da seção do card, com respiro antes do conteúdo."""
        h = QHBoxLayout()
        h.setSpacing(tema.ESP_M)
        v = QVBoxLayout()
        v.setSpacing(3)
        v.addWidget(rotulo(texto, "secao"))
        if sub:
            v.addWidget(rotulo(sub, "secao_sub", quebra=True))
        h.addLayout(v, 1)
        if direita is not None:
            h.addWidget(direita, 0, Qt.AlignmentFlag.AlignTop)
        self.lay.addLayout(h)
        self.lay.addSpacing(tema.ESP_XS)

    def mouseReleaseEvent(self, e) -> None:
        if self._clicavel and e.button() == Qt.MouseButton.LeftButton:
            self.clicado.emit()
        super().mouseReleaseEvent(e)


class CardFuncao(Card):
    """Card grande da tela inicial: ícone, título, descrição e chamada."""

    def __init__(self, icone: str, titulo: str, descricao: str, cor: str, chamada: str = "Começar") -> None:
        super().__init__(clicavel=True)
        self.setMinimumHeight(214)
        self.lay.setSpacing(0)
        ic = QLabel()
        ic.setFixedSize(46, 46)
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic.setPixmap(icones.pixmap(icone, cor, 22))
        ic.setStyleSheet(f"background: {tema.mistura(cor, 0.14)}; border-radius: 12px;")
        self.lay.addWidget(ic)
        self.lay.addSpacing(tema.ESP_L)
        self.lay.addWidget(rotulo(titulo, "secao"))
        self.lay.addSpacing(6)
        d = rotulo(descricao, "suave", quebra=True)
        d.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.lay.addWidget(d)
        self.lay.addStretch()
        self.lay.addSpacing(tema.ESP_L)
        c = QLabel(f"{chamada}  →")
        c.setStyleSheet(f"color: {cor}; font-weight: 650;")
        self.lay.addWidget(c)


class Tile(QFrame):
    """Número em destaque com rótulo (estatísticas)."""

    def __init__(self, titulo: str, valor: str = "—", sub: str = "", cor: str = tema.TEXTO) -> None:
        super().__init__()
        self.setProperty("papel", "tile")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(6)
        self.l_titulo = rotulo(titulo.upper(), "rotulo")
        self.l_valor = QLabel(valor)
        self.l_valor.setStyleSheet(f"font-size: 18pt; font-weight: 700; color: {cor};")
        self.l_sub = rotulo(sub, "suave")
        self.l_sub.setStyleSheet(f"color: {tema.APAGADO}; font-size: 8.5pt;")
        self.l_sub.setText(sub or " ")   # mantém a altura igual entre tiles
        lay.addWidget(self.l_titulo)
        lay.addWidget(self.l_valor)
        lay.addWidget(self.l_sub)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def definir(self, valor: str, sub: str | None = None, cor: str | None = None) -> None:
        self.l_valor.setText(valor)
        if sub is not None:
            self.l_sub.setText(sub or " ")
        if cor:
            self.l_valor.setStyleSheet(f"font-size: 18pt; font-weight: 700; color: {cor};")


class Pill(QLabel):
    """Etiqueta de status com cor. Com ``pulsar`` o ponto pisca (rodando)."""

    def __init__(self, texto: str = "", cor: str = tema.SUAVE) -> None:
        super().__init__()
        self._cor = cor
        self._fase = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._piscar)
        self.definir(texto, cor)

    def definir(self, texto: str, cor: str, pulsar: bool = False) -> None:
        self._cor = cor
        self._texto = texto
        self._render(1.0)
        if pulsar and not self._timer.isActive():
            self._timer.start(60)
        elif not pulsar:
            self._timer.stop()

    def _render(self, alfa: float) -> None:
        c = QColor(self._cor)
        ponto = f"rgba({c.red()},{c.green()},{c.blue()},{alfa:.2f})"
        self.setText(f"<span style='color:{ponto}'>●</span>&nbsp; {html.escape(self._texto)}")
        self.setStyleSheet(f"background: {tema.mistura(self._cor, 0.13)}; color: {self._cor}; "
                           f"border: 1px solid {tema.mistura(self._cor, 0.35)};"
                           "border-radius: 11px; padding: 3px 11px; font-weight: 600; font-size: 9pt;")

    def _piscar(self) -> None:
        import math
        self._fase += 1
        self._render(0.35 + 0.65 * (0.5 + 0.5 * math.sin(self._fase / 4)))


class ProgressoAnimado(QProgressBar):
    """Barra que desliza até o novo valor e mostra um brilho correndo enquanto ativa."""

    def __init__(self) -> None:
        super().__init__()
        self.setRange(0, 1000)
        self.setTextVisible(False)
        self.setFixedHeight(14)
        self._anim = QPropertyAnimation(self, b"value", self)
        self._anim.setDuration(450)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._brilho = 0.0
        self.ativo = False
        self._t = QTimer(self)
        self._t.timeout.connect(self._mover)
        self._t.start(30)

    def ir_para(self, fracao: float) -> None:
        alvo = int(max(0.0, min(1.0, fracao)) * 1000)
        if alvo == self.value():
            return
        self._anim.stop()
        self._anim.setStartValue(self.value())
        self._anim.setEndValue(alvo)
        self._anim.start()

    def _mover(self) -> None:
        if self.ativo:
            self._brilho = (self._brilho + 0.012) % 1.3
            self.update()

    def paintEvent(self, e) -> None:
        super().paintEvent(e)
        if not self.ativo or self.value() <= 0:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width() * self.value() / 1000
        x = (self._brilho - 0.15) * w
        g_w = max(30.0, w * 0.18)
        grad = QLinearGradient(x, 0, x + g_w, 0)
        grad.setColorAt(0, QColor(255, 255, 255, 0))
        grad.setColorAt(0.5, QColor(255, 255, 255, 90))
        grad.setColorAt(1, QColor(255, 255, 255, 0))
        p.setClipRect(QRectF(0, 0, w, self.height()))
        p.setBrush(grad)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(0, 0, w, self.height()), 6, 6)
        p.end()


class Spinner(QWidget):
    """Arco girando (indicador de atividade)."""

    def __init__(self, tamanho: int = 18, cor: str = tema.VERDE) -> None:
        super().__init__()
        self.setFixedSize(tamanho, tamanho)
        self._ang = 0
        self._cor = QColor(cor)
        self._t = QTimer(self)
        self._t.timeout.connect(self._girar)

    def iniciar(self) -> None:
        self._t.start(16)
        self.show()

    def parar(self) -> None:
        self._t.stop()
        self.hide()

    def _girar(self) -> None:
        self._ang = (self._ang + 7) % 360
        self.update()

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self._cor, 2.4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        r = QRectF(2, 2, self.width() - 4, self.height() - 4)
        p.drawArc(r, -self._ang * 16, 270 * 16)
        p.end()


class LogView(QTextEdit):
    """Log colorido por nível, com rolagem automática e filtro."""

    NIVEIS_FILTRO = {"tudo": None, "avisos": {"aviso", "erro"}, "erros": {"erro"}, "sem debug": "-debug"}

    def __init__(self) -> None:
        super().__init__()
        self.setReadOnly(True)
        self.setFont(tema.fonte_mono(9))
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.setStyleSheet(f"background: #070B0F; border: 1px solid {tema.BORDA}; border-radius: 10px; padding: 8px;")
        self.document().setMaximumBlockCount(5000)
        self._linhas: list[tuple[str, str, str]] = []
        self._filtro = "sem debug"
        self.auto_rolar = True

    def adicionar(self, msg: str, nivel: str = "info") -> None:
        hora = dt.datetime.now().strftime("%H:%M:%S")
        self._linhas.append((hora, nivel, msg))
        if len(self._linhas) > 5000:
            self._linhas = self._linhas[-4000:]
        if self._passa(nivel):
            self._escrever(hora, nivel, msg)

    def _passa(self, nivel: str) -> bool:
        f = self.NIVEIS_FILTRO[self._filtro]
        if f is None:
            return True
        if f == "-debug":
            return nivel != "debug"
        return nivel in f

    def _escrever(self, hora: str, nivel: str, msg: str) -> None:
        cor = tema.COR_NIVEL.get(nivel, tema.TEXTO)
        tag = {"ok": "✔", "erro": "✖", "aviso": "▲", "etapa": "▸", "debug": "·"}.get(nivel, " ")
        peso = "font-weight:600;" if nivel == "etapa" else ""
        self.append(f"<span style='color:{tema.APAGADO}'>{hora}</span>&nbsp;"
                    f"<span style='color:{cor};{peso}'>{tag} {html.escape(msg)}</span>")
        if self.auto_rolar:
            self.moveCursor(QTextCursor.MoveOperation.End)

    def filtrar(self, chave: str) -> None:
        self._filtro = chave
        self.clear()
        for hora, nivel, msg in self._linhas[-1500:]:
            if self._passa(nivel):
                self._escrever(hora, nivel, msg)

    def texto_completo(self) -> str:
        return "\n".join(f"[{h}] {n.upper()} {m}" for h, n, m in self._linhas)


class IndicadorPassos(QWidget):
    """Passos do assistente: círculo numerado (✓ quando feito) + nome, ligados por trilho."""

    def __init__(self, passos: list[str]) -> None:
        super().__init__()
        self.passos = passos
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.lay = QHBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(10)
        self.circulos: list[QLabel] = []
        self.nomes: list[QLabel] = []
        self.trilhos: list[QFrame] = []
        for i, nome in enumerate(passos):
            c = QLabel()
            c.setFixedSize(26, 26)
            c.setAlignment(Qt.AlignmentFlag.AlignCenter)
            n = QLabel(nome)
            self.circulos.append(c)
            self.nomes.append(n)
            self.lay.addWidget(c)
            self.lay.addWidget(n)
            if i < len(passos) - 1:
                t = QFrame()
                t.setFixedHeight(2)
                t.setMinimumWidth(16)
                self.trilhos.append(t)
                self.lay.addWidget(t, 1)
        self.definir(0)

    def definir(self, i: int) -> None:
        self.atual = i
        for j, (c, n) in enumerate(zip(self.circulos, self.nomes)):
            if j < i:
                c.setText("✓")
                c.setStyleSheet(f"background: {tema.mistura(tema.VERDE, 0.16, tema.BG)}; color: {tema.VERDE};"
                                "border-radius: 13px; font-weight: 700;")
                n.setStyleSheet(f"color: {tema.SUAVE};")
            elif j == i:
                c.setText(str(j + 1))
                c.setStyleSheet(f"background: {tema.VERDE}; color: #04130C; border-radius: 13px; font-weight: 800;")
                n.setStyleSheet(f"color: {tema.TEXTO}; font-weight: 650;")
            else:
                c.setText(str(j + 1))
                c.setStyleSheet(f"background: transparent; color: {tema.APAGADO}; border: 1.5px solid {tema.BORDA};"
                                "border-radius: 13px; font-weight: 600;")
                n.setStyleSheet(f"color: {tema.APAGADO};")
        for j, t in enumerate(self.trilhos):
            t.setStyleSheet(f"background: {tema.VERDE_ESCURO if j < i else tema.BORDA}; border-radius: 1px;")

    def compacto(self, sim: bool) -> None:
        """Em telas estreitas, só o nome do passo atual aparece."""
        for j, n in enumerate(self.nomes):
            n.setVisible(not sim or j == self.atual)


class Banner(QFrame):
    """Faixa de atenção (ex.: resolver captcha no Chrome)."""

    def __init__(self, texto: str = "") -> None:
        super().__init__()
        self.setProperty("papel", "banner")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        ic = QLabel("⚠")
        ic.setStyleSheet(f"color: {tema.AMARELO}; font-size: 16pt;")
        lay.addWidget(ic)
        self.texto = rotulo(texto, quebra=True)
        self.texto.setStyleSheet(f"color: {tema.AMARELO}; font-weight: 600;")
        lay.addWidget(self.texto, 1)
        self.hide()

    def mostrar(self, texto: str) -> None:
        self.texto.setText(texto)
        self.show()


def caixa_v(*widgets, espaco: int = 10, margens=(0, 0, 0, 0)) -> QWidget:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(*margens)
    lay.setSpacing(espaco)
    for x in widgets:
        if isinstance(x, int):
            lay.addSpacing(x)
        elif x is None:
            lay.addStretch()
        else:
            lay.addWidget(x)
    return w


def caixa_h(*widgets, espaco: int = 10, margens=(0, 0, 0, 0)) -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(*margens)
    lay.setSpacing(espaco)
    for x in widgets:
        if isinstance(x, int):
            lay.addSpacing(x)
        elif x is None:
            lay.addStretch()
        else:
            lay.addWidget(x)
    return w


class GradeResponsiva(QWidget):
    """Distribui widgets em colunas conforme a largura disponível (como um grid CSS)."""

    def __init__(self, largura_min: int, max_colunas: int = 4, espaco: int = tema.ESP_L,
                 colunas_validas: tuple[int, ...] | None = None) -> None:
        super().__init__()
        self.largura_min = largura_min
        self.max_colunas = max_colunas
        # ex.: 3 cards -> (3, 1); 4 tiles -> (4, 2, 1): nunca deixa um item sozinho na última linha
        self.colunas_validas = colunas_validas
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.grade = QGridLayout(self)
        self.grade.setContentsMargins(0, 0, 0, 0)
        self.grade.setHorizontalSpacing(espaco)
        self.grade.setVerticalSpacing(espaco)
        self.itens: list[QWidget] = []
        self._cols = 0

    def adicionar(self, w: QWidget) -> None:
        self.itens.append(w)
        self._reorganizar(force=True)

    def colunas_para(self, largura: int) -> int:
        esp = self.grade.horizontalSpacing()
        cabe = max(1, min(self.max_colunas, len(self.itens) or 1, (largura + esp) // (self.largura_min + esp)))
        if self.colunas_validas:
            cabe = max([c for c in self.colunas_validas if c <= cabe] or [1])
        return cabe

    def _reorganizar(self, force: bool = False) -> None:
        cols = self.colunas_para(self.width() or self.largura_min * self.max_colunas)
        if cols == self._cols and not force:
            return
        self._cols = cols
        for w in self.itens:
            self.grade.removeWidget(w)
        for i, w in enumerate(self.itens):
            self.grade.addWidget(w, i // cols, i % cols)
        for c in range(self.max_colunas):
            self.grade.setColumnStretch(c, 1 if c < cols else 0)

    def resizeEvent(self, e) -> None:
        self._reorganizar()
        super().resizeEvent(e)


class CardForm(Card):
    """Card de formulário: cada linha tem rótulo (e ajuda) à esquerda e o campo à
    direita com largura máxima. Abaixo de ~720 px de largura, empilha rótulo e campo."""

    def __init__(self, titulo: str = "", sub: str = "") -> None:
        super().__init__()
        if titulo:
            self.titulo(titulo, sub)
        self.grade = QGridLayout()
        self.grade.setHorizontalSpacing(tema.ESP_XL)
        self.grade.setVerticalSpacing(tema.ESP_L)
        self.grade.setColumnMinimumWidth(0, 210)
        self.grade.setColumnStretch(1, 1)
        self.lay.addLayout(self.grade)
        self.linhas: list[tuple[QWidget, QWidget]] = []
        self._empilhado = None

    def campo(self, titulo: str, widget: QWidget, ajuda: str = "", largura: int = 440) -> QWidget:
        bloco = QWidget()
        v = QVBoxLayout(bloco)
        v.setContentsMargins(0, 2, 0, 0)
        v.setSpacing(3)
        if titulo:
            t = QLabel(titulo)
            t.setStyleSheet("font-weight: 600;")
            v.addWidget(t)
        if ajuda:
            a = rotulo(ajuda, "suave", quebra=True)
            a.setStyleSheet(f"color: {tema.SUAVE}; font-size: 9pt;")
            v.addWidget(a)
        caixa = QWidget()
        h = QHBoxLayout(caixa)
        h.setContentsMargins(0, 0, 0, 0)
        widget.setMaximumWidth(largura)
        h.addWidget(widget, 1)
        h.addStretch(0)
        self.linhas.append((bloco, caixa))
        self._posicionar(len(self.linhas) - 1)
        return widget

    def _posicionar(self, i: int) -> None:
        bloco, caixa = self.linhas[i]
        if self._empilhado:
            self.grade.addWidget(bloco, 2 * i, 0, 1, 2)
            self.grade.addWidget(caixa, 2 * i + 1, 0, 1, 2)
        else:
            self.grade.addWidget(bloco, i, 0, Qt.AlignmentFlag.AlignTop)
            self.grade.addWidget(caixa, i, 1, Qt.AlignmentFlag.AlignTop)

    def resizeEvent(self, e) -> None:
        emp = self.width() < 720
        if emp != self._empilhado:
            self._empilhado = emp
            for bloco, caixa in self.linhas:
                self.grade.removeWidget(bloco)
                self.grade.removeWidget(caixa)
            self.grade.setColumnMinimumWidth(0, 0 if emp else 210)
            for i in range(len(self.linhas)):
                self._posicionar(i)
        super().resizeEvent(e)

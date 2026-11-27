"""Abertura animada: chuva estilo Matrix, a arte ASCII "decodificando" no centro e o
nome do programa sendo digitado. Clique, Esc, Enter ou espaço pulam."""
from __future__ import annotations

import math
import random

from PySide6.QtCore import QElapsedTimer, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QGuiApplication, QPainter, QRadialGradient
from PySide6.QtWidgets import QWidget

from .. import __version__
from ..filtros import _pasta_dados
from . import tema

GLIFOS = ("ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ"
          "0123456789ABCDEFXZ$#*+=<>:;"
          "LATTESCNPQ")
VERDE = QColor(tema.VERDE)


def carregar_arte() -> list[str]:
    try:
        return (_pasta_dados() / "ascii_accioly.txt").read_text(encoding="utf-8").rstrip("\n").splitlines()
    except OSError:
        return ["ACCIOLY"]


class _Gota:
    __slots__ = ("y", "vel", "tam")

    def __init__(self, linhas: int, inicio: bool) -> None:
        self.y = random.uniform(-linhas, linhas if inicio else 0)
        self.vel = random.uniform(0.25, 0.85)
        self.tam = random.randint(6, 26)


class Intro(QWidget):
    terminou = Signal()

    T_ARTE = 700         # começa a decodificar a arte
    T_ARTE_FIM = 2300
    T_TITULO = 2500
    T_SUB = 3700
    DURACAO = 5600
    FADE = 650

    def __init__(self, parent=None, duracao_ms: int | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.duracao = duracao_ms or self.DURACAO
        tela = QGuiApplication.primaryScreen().availableGeometry() if QGuiApplication.primaryScreen() else None
        w, h = (min(1180, int(tela.width() * 0.8)), min(700, int(tela.height() * 0.8))) if tela else (1180, 700)
        self.resize(w, h)
        if tela:
            self.move(tela.center().x() - w // 2, tela.center().y() - h // 2)

        self.fonte_chuva = tema.fonte_mono(13)
        fm = QFontMetricsF(self.fonte_chuva)
        self.cel_w = fm.horizontalAdvance("ｱ") + 2
        self.cel_h = fm.height()
        self.arte = carregar_arte()
        self._montar_chuva()
        self._montar_arte()
        self.titulo = "EXTRATOR CNPq LATTES"
        self.sub = f"coleta · busca por nomes · planilhas      v{__version__}"

        self.relogio = QElapsedTimer()
        self.relogio.start()
        self._tempo_fixo: int | None = None
        self._fechando = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._passo)
        self.timer.start(33)

    # ------------------------------------------------------------ preparação
    def _montar_chuva(self) -> None:
        self.cols = max(10, int(self.width() / self.cel_w) + 1)
        self.linhas = int(self.height() / self.cel_h) + 2
        self.gotas = [_Gota(self.linhas, True) for _ in range(self.cols)]
        self.chars = [[random.choice(GLIFOS) for _ in range(self.linhas)] for _ in range(self.cols)]

    def _montar_arte(self) -> None:
        largura = max(len(l) for l in self.arte)
        tam = 14
        f = tema.fonte_mono(tam)
        while tam > 6:
            f = tema.fonte_mono(tam)
            f.setBold(True)
            if QFontMetricsF(f).horizontalAdvance("M") * largura < self.width() * 0.82:
                break
            tam -= 1
        self.fonte_arte = f
        fm = QFontMetricsF(f)
        self.arte_cw, self.arte_ch = fm.horizontalAdvance("M"), fm.height() * 0.92
        x0 = (self.width() - self.arte_cw * largura) / 2
        y0 = self.height() * 0.40 - self.arte_ch * len(self.arte) / 2
        self.celulas = []  # (x, y, char, revela_ms)
        for li, linha in enumerate(self.arte):
            for ci, ch in enumerate(linha):
                if ch == " ":
                    continue
                frac = ci / max(1, largura)
                revela = self.T_ARTE + frac * (self.T_ARTE_FIM - self.T_ARTE - 400) + random.uniform(0, 400)
                self.celulas.append((x0 + ci * self.arte_cw, y0 + li * self.arte_ch, ch, revela))
        self.base_arte = y0 + len(self.arte) * self.arte_ch

    def resizeEvent(self, e) -> None:
        self._montar_chuva()
        self._montar_arte()
        super().resizeEvent(e)

    # ---------------------------------------------------------------- tempo
    def agora(self) -> int:
        return self._tempo_fixo if self._tempo_fixo is not None else self.relogio.elapsed()

    def quadro_em(self, ms: int) -> None:
        """Avança a animação até ``ms`` sem tempo real (usado para capturas)."""
        self.timer.stop()
        passos = int(ms / 33)
        for _ in range(min(passos, 400)):
            self._avancar_chuva()
        self._tempo_fixo = ms
        self.update()

    def _avancar_chuva(self) -> None:
        for i, g in enumerate(self.gotas):
            g.y += g.vel
            if g.y - g.tam > self.linhas:
                self.gotas[i] = _Gota(self.linhas, False)
            if random.random() < 0.06:
                self.chars[i][random.randrange(self.linhas)] = random.choice(GLIFOS)

    def _passo(self) -> None:
        self._avancar_chuva()
        t = self.agora()
        if t >= self.duracao - self.FADE:
            self.setWindowOpacity(max(0.0, (self.duracao - t) / self.FADE))
        if t >= self.duracao:
            self.terminar()
            return
        self.update()

    def terminar(self) -> None:
        if self._fechando:
            return
        self._fechando = True
        self.timer.stop()
        self.terminou.emit()
        self.close()

    def mousePressEvent(self, e) -> None:
        self.terminar()

    def keyPressEvent(self, e) -> None:
        if e.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.terminar()

    # -------------------------------------------------------------- desenho
    def paintEvent(self, _e) -> None:
        t = self.agora()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.fillRect(self.rect(), QColor("#000000"))

        # chuva
        p.setFont(self.fonte_chuva)
        for c, g in enumerate(self.gotas):
            x = c * self.cel_w
            cabeca = int(g.y)
            for k in range(g.tam):
                lin = cabeca - k
                if lin < 0 or lin >= self.linhas:
                    continue
                if k == 0:
                    cor = QColor("#D8FFE9")
                else:
                    a = int(220 * (1 - k / g.tam) ** 1.4)
                    cor = QColor(VERDE.red(), VERDE.green(), VERDE.blue(), a)
                p.setPen(cor)
                p.drawText(QPointF(x, lin * self.cel_h), self.chars[c][lin])

        # escurece o centro para destacar a arte
        grad = QRadialGradient(QPointF(self.width() / 2, self.height() * 0.45), self.width() * 0.55)
        grad.setColorAt(0.0, QColor(0, 0, 0, 225))
        grad.setColorAt(0.6, QColor(0, 0, 0, 150))
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(self.rect(), grad)

        # arte ASCII decodificando
        p.setFont(self.fonte_arte)
        for x, y, ch, revela in self.celulas:
            if t < revela - 450:
                continue
            if t < revela:
                p.setPen(QColor(150, 255, 200, 200))
                p.drawText(QPointF(x, y), random.choice(GLIFOS))
            else:
                brilho = max(0.0, 1 - (t - revela) / 500)
                p.setPen(QColor(46, 229, 157, 70))
                p.drawText(QPointF(x + 1, y + 1), ch)
                cor = QColor(int(46 + 200 * brilho), int(229 + 26 * brilho), int(157 + 98 * brilho))
                p.setPen(cor)
                p.drawText(QPointF(x, y), ch)

        # título digitado
        if t >= self.T_TITULO:
            n = min(len(self.titulo), int((t - self.T_TITULO) / 55) + 1)
            f = tema.fonte_mono(24)
            f.setBold(True)
            f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 112)
            p.setFont(f)
            fm = QFontMetricsF(f)
            txt = self.titulo[:n]
            w_total = fm.horizontalAdvance(self.titulo)
            x0 = (self.width() - w_total) / 2
            y = self.base_arte + 70
            p.setPen(QColor(46, 229, 157, 60))
            p.drawText(QPointF(x0 + 2, y + 2), txt)
            p.setPen(QColor("#EFFFF6"))
            p.drawText(QPointF(x0, y), txt)
            if (t // 420) % 2 == 0 or n < len(self.titulo):
                p.fillRect(QRectF(x0 + fm.horizontalAdvance(txt) + 4, y - fm.ascent() + 4, fm.averageCharWidth() * 0.9,
                                  fm.ascent() - 2), VERDE)

        if t >= self.T_SUB:
            a = min(255, int((t - self.T_SUB) / 500 * 255))
            f = tema.fonte_mono(11)
            p.setFont(f)
            p.setPen(QColor(143, 161, 179, a))
            fm = QFontMetricsF(f)
            p.drawText(QPointF((self.width() - fm.horizontalAdvance(self.sub)) / 2, self.base_arte + 112), self.sub)

        # dica e borda
        f = tema.fonte_mono(9)
        p.setFont(f)
        p.setPen(QColor(93, 110, 126, 160 + int(60 * math.sin(t / 300))))
        dica = "clique para pular"
        p.drawText(QPointF(self.width() - QFontMetricsF(f).horizontalAdvance(dica) - 18, self.height() - 16), dica)
        p.setPen(QColor(46, 229, 157, 60))
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))
        p.end()

"""Desenha o ícone do programa (PNG e ICO) em lattes_extrator/data/.

Uso: QT_QPA_PLATFORM=offscreen python tools/gerar_icone.py
"""
import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QLinearGradient, QPainter, QPen

DESTINO = Path(__file__).resolve().parent.parent / "lattes_extrator" / "data"


def desenhar(tam: int) -> QImage:
    img = QImage(tam, tam, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    r = QRectF(tam * 0.04, tam * 0.04, tam * 0.92, tam * 0.92)
    g = QLinearGradient(0, 0, 0, tam)
    g.setColorAt(0, QColor("#0F1C26"))
    g.setColorAt(1, QColor("#05090C"))
    p.setBrush(g)
    p.setPen(QPen(QColor("#2EE59D"), max(1.0, tam * 0.035)))
    p.drawRoundedRect(r, tam * 0.2, tam * 0.2)
    f = QFont("DejaVu Sans Mono")
    f.setPixelSize(int(tam * 0.56))
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor("#2EE59D"))
    p.drawText(r.adjusted(0, -tam * 0.04, 0, 0), Qt.AlignmentFlag.AlignCenter, "L▌")
    p.end()
    return img


def main() -> int:
    QGuiApplication(sys.argv)
    DESTINO.mkdir(parents=True, exist_ok=True)
    desenhar(256).save(str(DESTINO / "icone.png"))
    desenhar(256).save(str(DESTINO / "icone.ico"))
    print(DESTINO / "icone.png", DESTINO / "icone.ico")
    return 0


if __name__ == "__main__":
    sys.exit(main())

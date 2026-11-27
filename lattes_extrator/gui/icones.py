"""Ícones em SVG (traço, estilo linha), coloridos em tempo de execução."""
from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

# Caminhos 24x24, traço 1.8 (inspirados no conjunto Lucide, desenhados à mão)
CAMINHOS = {
    "inicio": '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V20a1 1 0 0 0 1 1h4v-6h4v6h4a1 1 0 0 0 1-1V9.5"/>',
    "busca": '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    "nomes": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.8-3.6 3.4-5.5 6.5-5.5s5.7 1.9 6.5 5.5"/>'
             '<path d="M16 4.5a3.5 3.5 0 0 1 0 7"/><path d="M18 14.8c1.9.7 3.1 2.4 3.5 5.2"/>',
    "planilha": '<rect x="3" y="3" width="18" height="18" rx="2.5"/><path d="M3 9h18M3 15h18M9 3v18"/>',
    "execucao": '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
    "extracoes": '<path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v4.5h4.5"/><path d="M12 7.5V12l3 2"/>',
    "config": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1'
              'a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3'
              'l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5'
              '-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1'
              ' 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7'
              ' 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
    "pasta": '<path d="M3 6.5A1.5 1.5 0 0 1 4.5 5H9l2 2.5h8.5A1.5 1.5 0 0 1 21 9v9.5a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 18.5z"/>',
    "seta": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "voltar": '<path d="M19 12H5M11 6l-6 6 6 6"/>',
    "pausa": '<path d="M9 5v14M15 5v14"/>',
    "play": '<path d="M7 4.5v15l12-7.5z"/>',
    "parar": '<rect x="6" y="6" width="12" height="12" rx="1.5"/>',
    "download": '<path d="M12 3v12M7 10l5 5 5-5M4 20h16"/>',
    "arquivo": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>',
    "mais": '<circle cx="5" cy="12" r="1.2"/><circle cx="12" cy="12" r="1.2"/><circle cx="19" cy="12" r="1.2"/>',
    "lixo": '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>',
    "refazer": '<path d="M21 12a9 9 0 1 1-3-6.7"/><path d="M21 4v4.5h-4.5"/>',
    "base": '<ellipse cx="12" cy="5.5" rx="8" ry="3"/><path d="M4 5.5v13c0 1.7 3.6 3 8 3s8-1.3 8-3v-13"/>'
            '<path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
    "externo": '<path d="M14 4h6v6M20 4l-9 9"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
    "codigo": '<path d="m8 8-5 4 5 4M16 8l5 4-5 4M13.5 5l-3 14"/>',
    "detalhe": '<path d="M2.5 12S6 5 12 5s9.5 7 9.5 7-3.5 7-9.5 7-9.5-7-9.5-7z"/><circle cx="12" cy="12" r="3"/>',
}


def svg(nome: str, cor: str, traco: float = 1.8) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{cor}" '
            f'stroke-width="{traco}" stroke-linecap="round" stroke-linejoin="round">{CAMINHOS[nome]}</svg>')


@lru_cache(maxsize=256)
def pixmap(nome: str, cor: str, tamanho: int = 18, escala: float = 2.0) -> QPixmap:
    lado = int(tamanho * escala)
    pm = QPixmap(lado, lado)
    pm.fill(Qt.GlobalColor.transparent)
    r = QSvgRenderer(QByteArray(svg(nome, cor).encode()))
    p = QPainter(pm)
    r.render(p)
    p.end()
    pm.setDevicePixelRatio(escala)
    return pm


def icone(nome: str, cor: str, cor_ativo: str | None = None, tamanho: int = 18) -> QIcon:
    """QIcon com cor normal e, se ``cor_ativo``, outra cor para o estado marcado (checked)."""
    ic = QIcon()
    ic.addPixmap(pixmap(nome, cor, tamanho), QIcon.Mode.Normal, QIcon.State.Off)
    ic.addPixmap(pixmap(nome, cor_ativo or cor, tamanho), QIcon.Mode.Normal, QIcon.State.On)
    ic.addPixmap(pixmap(nome, cor_ativo or cor, tamanho), QIcon.Mode.Active, QIcon.State.On)
    return ic


TAMANHO = QSize(18, 18)

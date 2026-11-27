"""Ponto de entrada da interface gráfica."""
from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from .. import NOME_APP
from ..config import Config
from . import tema


def preparar_webengine() -> None:
    """O QtWebEngine (visualizador do currículo original) precisa ser carregado antes
    do QApplication. É opcional: sem ele o visualizador usa o modo simplificado."""
    try:
        from PySide6 import QtWebEngineWidgets  # noqa: F401
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    except Exception:
        pass


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    preparar_webengine()
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(argv)
    app.setApplicationName(NOME_APP)
    app.setOrganizationName("Accioly")
    from PySide6.QtGui import QIcon
    from ..filtros import _pasta_dados
    app.setWindowIcon(QIcon(str(_pasta_dados() / "icone.png")))
    tema.aplicar(app)
    cfg = Config.carregar()

    from .janela import JanelaPrincipal
    janela = JanelaPrincipal(cfg)

    if cfg.mostrar_intro and "--sem-intro" not in argv:
        from .intro import Intro
        intro = Intro()
        intro.terminou.connect(janela.show)
        intro.show()
        app._intro = intro  # mantém referência
    else:
        janela.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

"""Paleta e folha de estilo (QSS) da interface."""
from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

BG = "#0A1016"
SUPERFICIE = "#111A23"
SUPERFICIE_2 = "#16222E"
SUPERFICIE_3 = "#1C2B39"
BORDA = "#22323F"
TEXTO = "#E6EDF3"
SUAVE = "#8FA1B3"
APAGADO = "#6B7D8F"
VERDE = "#2EE59D"        # acento "Matrix"
VERDE_ESCURO = "#14A86C"
AZUL = "#3BA7FF"
AMARELO = "#F5B841"
VERMELHO = "#FF6B6B"

# Escala de espaçamento (px) e tipografia (pt) — usar sempre estes valores
ESP_XS, ESP_S, ESP_M, ESP_L, ESP_XL, ESP_XXL = 4, 8, 12, 16, 24, 32
LARGURA_CONTEUDO = 1280
ROXO = "#A78BFA"

# Cores da página do CNPq (para a réplica do formulário de busca)
CNPQ_AZUL = "#326C99"
CNPQ_AZUL_ESCURO = "#1F4E79"
CNPQ_FUNDO = "#F4F6F8"
CNPQ_BORDA = "#C9D3DD"

COR_STATUS = {
    "novo": SUAVE, "rodando": VERDE, "pausado": AMARELO, "concluido": AZUL,
    "erro": VERMELHO, "cancelado": AMARELO,
}
COR_NIVEL = {"info": TEXTO, "ok": VERDE, "aviso": AMARELO, "erro": VERMELHO, "etapa": AZUL, "debug": APAGADO}


def mistura(cor: str, alfa: float = 0.14, fundo: str = SUPERFICIE) -> str:
    """Cor sólida equivalente a ``cor`` com transparência ``alfa`` sobre ``fundo``.
    (O Qt lê #RRGGBBAA como #AARRGGBB; misturar evita esse erro e funciona em HTML.)"""
    a, b = QColor(cor), QColor(fundo)
    r = [round(x * alfa + y * (1 - alfa)) for x, y in ((a.red(), b.red()), (a.green(), b.green()), (a.blue(), b.blue()))]
    return "#{:02X}{:02X}{:02X}".format(*r)


def _icone(nome: str, svg: str) -> str:
    """Grava um SVG pequeno numa pasta temporária e devolve o caminho (para o QSS)."""
    import tempfile
    from pathlib import Path
    pasta = Path(tempfile.gettempdir()) / "extrator-lattes-icones"
    pasta.mkdir(exist_ok=True)
    arq = pasta / f"{nome}.svg"
    if not arq.exists() or arq.read_text() != svg:
        arq.write_text(svg)
    return arq.as_posix()


CHECK_ESCURO = _icone("check-escuro", '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">'
                      '<path d="M3.5 8.2l3 3 6-6.4" fill="none" stroke="#04130C" stroke-width="2.2" '
                      'stroke-linecap="round" stroke-linejoin="round"/></svg>')
CHECK_BRANCO = _icone("check-branco", '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">'
                      '<path d="M3.5 8.2l3 3 6-6.4" fill="none" stroke="#FFFFFF" stroke-width="2.2" '
                      'stroke-linecap="round" stroke-linejoin="round"/></svg>')

SETA_CIMA = _icone("seta-cima", '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="6" viewBox="0 0 10 6"><path d="M1 5l4-4 4 4" fill="none" stroke="#8FA1B3" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>')
SETA_BAIXO = _icone("seta-baixo", '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="6" viewBox="0 0 10 6"><path d="M1 1l4 4 4-4" fill="none" stroke="#8FA1B3" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>')
SETA_CIMA_CNPQ = _icone("seta-cima-cnpq", '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="6" viewBox="0 0 10 6"><path d="M1 5l4-4 4 4" fill="none" stroke="#326C99" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>')
SETA_BAIXO_CNPQ = _icone("seta-baixo-cnpq", '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="6" viewBox="0 0 10 6"><path d="M1 1l4 4 4-4" fill="none" stroke="#326C99" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>')


def fonte_mono(tamanho: int = 10) -> QFont:
    f = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    for nome in ("JetBrains Mono", "Cascadia Mono", "Consolas", "DejaVu Sans Mono", "Menlo", "Monospace"):
        if nome in QFontDatabase.families():
            f = QFont(nome)
            break
    f.setPointSize(tamanho)
    f.setStyleHint(QFont.StyleHint.Monospace)
    return f


QSS = f"""
* {{ outline: none; }}
QWidget {{ background: transparent; color: {TEXTO}; font-size: 10pt; }}
QMainWindow, QStackedWidget, QMessageBox, QFileDialog {{ background: {BG}; }}
QToolTip {{ background: {SUPERFICIE_3}; color: {TEXTO}; border: 1px solid {BORDA}; padding: 6px; border-radius: 6px; }}
QLabel {{ background: transparent; }}
QLabel[papel="titulo"] {{ font-size: 21pt; font-weight: 700; }}
QLabel[papel="subtitulo"] {{ font-size: 10.5pt; color: {SUAVE}; }}
QLabel[papel="sobrelinha"] {{ font-size: 8.5pt; font-weight: 700; color: {VERDE}; letter-spacing: 1.5px; }}
QLabel[papel="secao"] {{ font-size: 12.5pt; font-weight: 650; }}
QLabel[papel="secao_sub"] {{ font-size: 9.5pt; color: {SUAVE}; }}
QLabel[papel="rotulo"] {{ color: {SUAVE}; font-size: 8.5pt; font-weight: 600; letter-spacing: 1px; }}
QLabel[papel="suave"] {{ color: {SUAVE}; }}
QLabel[papel="mono"] {{ color: {VERDE}; }}

#Sidebar {{ background: {SUPERFICIE}; border-right: 1px solid {BORDA}; }}
#Sidebar QPushButton {{ text-align: left; padding: 9px 12px; border: none; border-radius: 9px;
    color: {SUAVE}; background: transparent; font-size: 10pt; }}
#Sidebar QPushButton[compacto="true"] {{ text-align: center; padding: 10px 0; }}
#Sidebar QLabel[papel="grupo"] {{ color: {APAGADO}; font-size: 8pt; font-weight: 700; letter-spacing: 1.5px;
    padding: 18px 12px 6px 12px; }}
#Sidebar QPushButton:hover {{ background: {SUPERFICIE_2}; color: {TEXTO}; }}
#Sidebar QPushButton:checked {{ background: {SUPERFICIE_3}; color: {VERDE}; font-weight: 600; }}

QFrame[papel="card"] {{ background: {SUPERFICIE}; border: 1px solid {BORDA}; border-radius: 14px; }}
QFrame[papel="card"]:hover[clicavel="true"] {{ border: 1px solid {VERDE_ESCURO}; background: {SUPERFICIE_2}; }}
QFrame[papel="tile"] {{ background: {SUPERFICIE}; border: 1px solid {BORDA}; border-radius: 12px; }}
QFrame[papel="banner"] {{ background: #2A2210; border: 1px solid {AMARELO}; border-radius: 10px; }}
QFrame[papel="linha"] {{ background: {BORDA}; max-height: 1px; min-height: 1px; border: none; }}

QPushButton {{ background: {SUPERFICIE_2}; border: 1px solid {BORDA}; border-radius: 9px; padding: 8px 16px;
    min-height: 20px; }}
QPushButton:hover {{ background: {SUPERFICIE_3}; border-color: #2F4558; }}
QPushButton:pressed {{ background: {SUPERFICIE}; }}
QPushButton:disabled {{ color: {APAGADO}; background: {SUPERFICIE}; border-color: {SUPERFICIE_2}; }}
QPushButton[papel="primario"] {{ background: {VERDE}; color: #04130C; border: none; font-weight: 700; }}
QPushButton[papel="primario"]:hover {{ background: #5BF0B5; }}
QPushButton[papel="primario"]:disabled {{ background: #1D4C39; color: #4F7C69; }}
QPushButton[papel="perigo"] {{ background: transparent; color: {VERMELHO}; border: 1px solid #5A2A2E; }}
QPushButton[papel="perigo"]:hover {{ background: #2A1517; }}
QPushButton[papel="link"] {{ background: transparent; border: none; color: {AZUL}; padding: 4px 6px; }}
QPushButton[papel="link"]:hover {{ color: #7CC4FF; }}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit {{
    background: {SUPERFICIE_2}; border: 1px solid {BORDA}; border-radius: 8px; padding: 6px 9px;
    selection-background-color: {VERDE_ESCURO}; }}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {{ border-color: {VERDE_ESCURO}; }}
QAbstractSpinBox {{ padding-left: 10px; padding-right: 26px; }}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{ subcontrol-origin: border; width: 22px;
    border: none; border-left: 1px solid {BORDA}; background: transparent; }}
QAbstractSpinBox::up-button {{ subcontrol-position: top right; border-top-right-radius: 8px; }}
QAbstractSpinBox::down-button {{ subcontrol-position: bottom right; border-bottom-right-radius: 8px; }}
QAbstractSpinBox::up-button:hover, QAbstractSpinBox::down-button:hover {{ background: {SUPERFICIE_3}; }}
QAbstractSpinBox::up-arrow {{ image: url({SETA_CIMA}); width: 10px; height: 6px; }}
QAbstractSpinBox::down-arrow {{ image: url({SETA_BAIXO}); width: 10px; height: 6px; }}
QComboBox::down-arrow {{ image: url({SETA_BAIXO}); width: 10px; height: 6px; }}
QComboBox QAbstractItemView {{ background: {SUPERFICIE_2}; border: 1px solid {BORDA}; selection-background-color: {SUPERFICIE_3}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QCheckBox, QRadioButton {{ spacing: 8px; background: transparent; }}
QCheckBox::indicator, QRadioButton::indicator {{ width: 16px; height: 16px; }}
QCheckBox::indicator {{ border: 1px solid #3A5163; border-radius: 4px; background: {SUPERFICIE_2}; }}
QCheckBox::indicator:checked {{ background: {VERDE}; border-color: {VERDE}; image: url({CHECK_ESCURO}); }}
QRadioButton::indicator {{ border: 1px solid #3A5163; border-radius: 8px; background: {SUPERFICIE_2}; }}
QRadioButton::indicator:checked {{ background: {VERDE}; border: 4px solid {SUPERFICIE_2}; }}

QProgressBar {{ background: {SUPERFICIE_2}; border: none; border-radius: 6px; height: 12px; text-align: center; color: transparent; }}
QProgressBar::chunk {{ border-radius: 6px; background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {VERDE_ESCURO}, stop:1 {VERDE}); }}

QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {SUPERFICIE_3}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #2C4153; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {SUPERFICIE_3}; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}

QTableWidget, QTableView, QListWidget {{ background: {SUPERFICIE}; border: 1px solid {BORDA}; border-radius: 10px;
    gridline-color: {BORDA}; alternate-background-color: {SUPERFICIE_2}; selection-background-color: {SUPERFICIE_3};
    selection-color: {TEXTO}; }}
QHeaderView::section {{ background: {SUPERFICIE_2}; color: {SUAVE}; border: none; border-bottom: 1px solid {BORDA};
    padding: 10px 12px; font-weight: 600; font-size: 9pt; }}
QTableView::item {{ padding: 0 12px; border-bottom: 1px solid {BORDA}; }}
QTableCornerButton::section {{ background: {SUPERFICIE_2}; border: none; }}
QGroupBox {{ border: 1px solid {BORDA}; border-radius: 12px; margin-top: 14px; padding: 16px 14px 12px 14px; background: {SUPERFICIE}; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 14px; padding: 0 6px; color: {SUAVE}; font-weight: 600; }}
QListWidget#ListaSecoes {{ padding: 6px; }}
QListWidget#ListaSecoes::item {{ padding: 7px 10px; border-radius: 7px; color: {SUAVE}; }}
QListWidget#ListaSecoes::item:hover {{ background: {SUPERFICIE_2}; color: {TEXTO}; }}
QListWidget#ListaSecoes::item:selected {{ background: {SUPERFICIE_3}; color: {VERDE}; }}
QTabWidget::pane {{ border: none; border-top: 1px solid {BORDA}; top: -1px; }}
QTabBar {{ background: transparent; }}
QTabBar::tab {{ background: transparent; color: {SUAVE}; padding: 10px 18px; border: none;
    border-bottom: 2px solid transparent; font-weight: 600; margin-right: 4px; }}
QTabBar::tab:hover {{ color: {TEXTO}; }}
QTabBar::tab:selected {{ color: {VERDE}; border-bottom: 2px solid {VERDE}; }}
QTextBrowser {{ background: {SUPERFICIE}; border: 1px solid {BORDA}; border-radius: 10px; padding: 6px; }}
QSplitter::handle {{ background: transparent; }}
QMenu {{ background: {SUPERFICIE_2}; border: 1px solid {BORDA}; padding: 4px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: {SUPERFICIE_3}; }}
QDialog {{ background: {SUPERFICIE}; }}
"""


def aplicar(app: QApplication) -> None:
    app.setStyle("Fusion")
    pal = QPalette()
    for papel, cor in (
        (QPalette.ColorRole.Window, BG), (QPalette.ColorRole.Base, SUPERFICIE_2),
        (QPalette.ColorRole.AlternateBase, SUPERFICIE), (QPalette.ColorRole.Text, TEXTO),
        (QPalette.ColorRole.WindowText, TEXTO), (QPalette.ColorRole.Button, SUPERFICIE_2),
        (QPalette.ColorRole.ButtonText, TEXTO), (QPalette.ColorRole.Highlight, VERDE_ESCURO),
        (QPalette.ColorRole.HighlightedText, "#FFFFFF"), (QPalette.ColorRole.ToolTipBase, SUPERFICIE_3),
        (QPalette.ColorRole.ToolTipText, TEXTO), (QPalette.ColorRole.PlaceholderText, APAGADO),
    ):
        pal.setColor(papel, QColor(cor))
    app.setPalette(pal)
    f = app.font()
    for nome in ("Inter", "Segoe UI Variable", "Segoe UI", "SF Pro Text", "Ubuntu", "Cantarell", "Noto Sans"):
        if nome in QFontDatabase.families():
            f = QFont(nome)
            break
    f.setPointSize(10)
    app.setFont(f)
    app.setStyleSheet(QSS)


# Folha de estilo da réplica da página do CNPq (clara, como o site)
QSS_CNPQ = f"""
QFrame#CnpqPagina {{ background: #FFFFFF; border: 1px solid {CNPQ_BORDA}; border-radius: 10px; }}
QFrame#CnpqPagina QWidget {{ background: transparent; color: #333333; font-family: Arial, Helvetica, sans-serif; font-size: 9.5pt; }}
QFrame#CnpqPagina QLabel[cnpq="titulo"] {{ color: {CNPQ_AZUL}; font-size: 15pt; font-weight: bold; }}
QFrame#CnpqPagina QLabel[cnpq="legenda"] {{ color: {CNPQ_AZUL_ESCURO}; font-weight: bold; font-size: 10pt; }}
QFrame#CnpqPagina QLabel[cnpq="ajuda"] {{ color: #666666; font-size: 8.5pt; }}
QFrame#CnpqPagina QFrame[cnpq="barra"] {{ background: {CNPQ_AZUL}; border-radius: 0px; }}
QFrame#CnpqPagina QFrame[cnpq="barra"] QLabel {{ color: #FFFFFF; font-weight: bold; font-size: 10pt; }}
QFrame#CnpqPagina QFrame[cnpq="caixa"] {{ background: {CNPQ_FUNDO}; border: 1px solid {CNPQ_BORDA}; border-radius: 4px; }}
QFrame#CnpqPagina QLineEdit, QFrame#CnpqPagina QComboBox, QFrame#CnpqPagina QSpinBox {{
    background: #FFFFFF; color: #222222; border: 1px solid #9FB1C2; border-radius: 3px; padding: 4px 6px; }}
QFrame#CnpqPagina QAbstractSpinBox {{ padding-right: 22px; }}
QFrame#CnpqPagina QAbstractSpinBox::up-button, QFrame#CnpqPagina QAbstractSpinBox::down-button {{
    subcontrol-origin: border; width: 18px; border: none; border-left: 1px solid #C9D3DD; background: #F4F6F8; }}
QFrame#CnpqPagina QAbstractSpinBox::up-button {{ subcontrol-position: top right; }}
QFrame#CnpqPagina QAbstractSpinBox::down-button {{ subcontrol-position: bottom right; }}
QFrame#CnpqPagina QAbstractSpinBox::up-arrow {{ image: url({SETA_CIMA_CNPQ}); width: 10px; height: 6px; }}
QFrame#CnpqPagina QAbstractSpinBox::down-arrow {{ image: url({SETA_BAIXO_CNPQ}); width: 10px; height: 6px; }}
QFrame#CnpqPagina QComboBox::down-arrow {{ image: url({SETA_BAIXO_CNPQ}); width: 10px; height: 6px; }}
QFrame#CnpqPagina QComboBox QAbstractItemView {{ background: #FFFFFF; color: #222222; selection-background-color: #DCE8F3; selection-color: #000; }}
QFrame#CnpqPagina QCheckBox::indicator, QFrame#CnpqPagina QRadioButton::indicator {{ background: #FFFFFF; border: 1px solid #7A8C9D; }}
QFrame#CnpqPagina QCheckBox::indicator:checked {{ background: {CNPQ_AZUL}; border-color: {CNPQ_AZUL}; image: url({CHECK_BRANCO}); }}
QFrame#CnpqPagina QCheckBox::indicator {{ border-radius: 3px; }}
QFrame#CnpqPagina QRadioButton::indicator:checked {{ background: {CNPQ_AZUL}; border: 4px solid #FFFFFF; }}
QFrame#CnpqPagina QPushButton {{ background: {CNPQ_AZUL}; color: #FFFFFF; border: none; border-radius: 3px; padding: 6px 14px; font-weight: bold; }}
QFrame#CnpqPagina QPushButton:hover {{ background: {CNPQ_AZUL_ESCURO}; }}
QFrame#CnpqPagina QPushButton[cnpq="link"] {{ background: transparent; color: {CNPQ_AZUL}; padding: 2px; text-decoration: underline; font-weight: normal; }}
"""

QSS_CNPQ_MODAL = f"""
QDialog {{ background: #FFFFFF; }}
QDialog QWidget {{ background: transparent; color: #333333; font-family: Arial, Helvetica, sans-serif; font-size: 9.5pt; }}
QDialog QFrame[cnpq="barra"] {{ background: {CNPQ_AZUL}; }}
QDialog QFrame[cnpq="barra"] QLabel {{ color: #FFFFFF; font-weight: bold; font-size: 10.5pt; }}
QDialog QLineEdit, QDialog QComboBox, QDialog QSpinBox {{ background: #FFFFFF; color: #222; border: 1px solid #9FB1C2; border-radius: 3px; padding: 4px 6px; }}
QDialog QComboBox::down-arrow {{ image: url({SETA_BAIXO_CNPQ}); width: 10px; height: 6px; }}
QDialog QComboBox QAbstractItemView {{ background: #FFFFFF; color: #222; selection-background-color: #DCE8F3; selection-color: #000; }}
QDialog QCheckBox::indicator {{ background: #FFFFFF; border: 1px solid #7A8C9D; border-radius: 3px; }}
QDialog QCheckBox::indicator:checked {{ background: {CNPQ_AZUL}; border-color: {CNPQ_AZUL}; image: url({CHECK_BRANCO}); }}
QDialog QPushButton {{ background: {CNPQ_AZUL}; color: #FFFFFF; border: none; border-radius: 3px; padding: 6px 16px; font-weight: bold; }}
QDialog QPushButton:hover {{ background: {CNPQ_AZUL_ESCURO}; }}
QDialog QPushButton[cnpq="sec"] {{ background: #E5EBF1; color: {CNPQ_AZUL_ESCURO}; }}
QDialog QLabel[cnpq="rotulo"] {{ color: {CNPQ_AZUL_ESCURO}; font-weight: bold; }}
"""

# -*- mode: python ; coding: utf-8 -*-
# PyInstaller: gera dist/ExtratorLattes/ (pasta com o executável).
#   pyinstaller ExtratorLattes.spec --noconfirm --clean
# Para um único arquivo .exe (abre mais devagar), use:  ONEFILE=1 pyinstaller ExtratorLattes.spec
import os
import sys

ONEFILE = os.environ.get("ONEFILE") == "1"
icone = "lattes_extrator/data/icone.ico" if sys.platform.startswith("win") else "lattes_extrator/data/icone.png"

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[("lattes_extrator/data", "lattes_extrator/data")],
    hiddenimports=["lattes_extrator.gui.app", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineCore"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # QtNetwork/QtQml/QtQuick/QtWebChannel são necessários para o QtWebEngine (visualizador do currículo)
    excludes=["tkinter", "pandas", "numpy", "matplotlib", "IPython", "pytest", "PySide6.QtSql", "PySide6.QtTest",
              "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.QtCharts", "PySide6.QtDataVisualization",
              "PySide6.QtMultimedia", "PySide6.QtBluetooth", "PySide6.QtSensors", "PySide6.QtSerialPort"],
    noarchive=False,
    optimize=1,
)
# --- Poda do Qt -------------------------------------------------------------------
# Os hooks do PySide6 copiam o Qt inteiro (3D, Quick3D, Charts, Multimedia...). Só ficam
# as bibliotecas que a interface e o QtWebEngine realmente carregam (fecho de dependências
# calculado com ldd) e os plugins de plataforma. Reduz o executável em ~300 MB.
import re as _re

QT_NECESSARIOS = {
    "Core", "Gui", "Widgets", "Svg", "Network", "DBus", "OpenGL", "OpenGLWidgets", "PrintSupport", "Positioning",
    "Qml", "QmlMeta", "QmlModels", "QmlWorkerScript", "Quick", "QuickWidgets", "WebChannel", "WebEngineCore",
    "WebEngineWidgets", "XcbQpa", "WaylandClient", "WlShellIntegration", "EglFSDeviceIntegration", "EglFsKmsSupport",
}
IDIOMAS = ("pt_BR", "pt-BR", "en-US", "en_US", "pt.")


def _manter(destino: str) -> bool:
    d = destino.replace("\\", "/")
    m = _re.search(r"(?:^|/)(?:lib)?Qt6([A-Za-z0-9]+)\.(?:so|dll|dylib)", d)
    if m and "/plugins/" not in d:
        return m.group(1) in QT_NECESSARIOS
    if "/Qt/qml/" in d or "/qml/" in d.lower() and "PySide6" in d:
        return False                                   # interface não usa QML
    if "devtools_resources" in d:
        return False                                   # ferramentas de desenvolvedor do Chromium
    if "/translations/" in d:
        return any(i in d for i in IDIOMAS) or d.endswith("qtwebengine_locales")
    return True


a.binaries = [b for b in a.binaries if _manter(b[0])]
a.datas = [x for x in a.datas if _manter(x[0])]

pyz = PYZ(a.pure)

if ONEFILE:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="ExtratorLattes", debug=False,
              bootloader_ignore_signals=False, strip=False, upx=False, runtime_tmpdir=None,
              console=False, disable_windowed_traceback=False, icon=icone)
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ExtratorLattes", debug=False,
              bootloader_ignore_signals=False, strip=False, upx=False, console=False,
              disable_windowed_traceback=False, icon=icone)
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="ExtratorLattes")

"""Próxima versão a partir dos fragmentos towncrier pendentes em changelog.d/.

removal -> major · feature -> minor · bugfix/improvement/doc -> patch.
Só fragmentos misc (internos, não aparecem no changelog) não geram versão: acumulam para a próxima.
Uso: python ci/versao.py <última-tag ou vazio>   ->  imprime "X.Y.Z" ou "" (sem release)
"""
import re
import sys
from pathlib import Path

TIPOS = ("feature", "bugfix", "improvement", "removal", "doc", "misc")


def fragmentos(pasta: Path = Path("changelog.d")) -> list[str]:
    tipos = []
    for f in pasta.glob("*.md"):
        partes = f.name.split(".")
        if len(partes) >= 3 and partes[-2] in TIPOS:
            tipos.append(partes[-2])
    return tipos


def proxima(ultima: str, tipos: list[str]) -> str:
    if not [t for t in tipos if t != "misc"]:
        return ""
    m = re.match(r"v?(\d+)\.(\d+)\.(\d+)", ultima or "")
    if not m:  # primeira release: a versão que está no código
        codigo = Path("lattes_extrator/__init__.py").read_text(encoding="utf-8")
        return re.search(r'__version__ = "(\d+\.\d+\.\d+)', codigo).group(1)
    major, minor, patch = map(int, m.groups())
    if "removal" in tipos:
        return f"{major + 1}.0.0"
    if "feature" in tipos:
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


if __name__ == "__main__":
    print(proxima(sys.argv[1] if len(sys.argv) > 1 else "", fragmentos()))

#!/usr/bin/env bash
# Grava a versão do build em lattes_extrator/__init__.py (só na cópia de trabalho do CI).
set -euo pipefail
VERSAO="${1:?versão}"
cd "$(dirname "$0")/.."
# "python" primeiro: no Windows, "python3" pode ser o atalho da Microsoft Store
PYBIN="$(command -v python || command -v python3)"
"$PYBIN" - "$VERSAO" <<'PY'
import re, sys
p = "lattes_extrator/__init__.py"
s = open(p, encoding="utf-8").read()
s = re.sub(r'__version__ = "[^"]*"', f'__version__ = "{sys.argv[1]}"', s)
open(p, "w", encoding="utf-8", newline="\n").write(s)
PY
grep -n "__version__" lattes_extrator/__init__.py

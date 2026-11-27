#!/usr/bin/env bash
# Gera o executável (Linux/macOS) em dist/ExtratorLattes/ExtratorLattes
set -euo pipefail
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
python -m pytest -q tests
pyinstaller ExtratorLattes.spec --noconfirm --clean
echo "Pronto: dist/ExtratorLattes/ExtratorLattes"

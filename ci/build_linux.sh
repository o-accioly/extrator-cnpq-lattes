#!/usr/bin/env bash
# Testes + executável Linux. Uso: ci/build_linux.sh <versão>   (gera dist-ci/*.tar.gz)
set -euo pipefail
VERSAO="${1:?versão}"
cd "$(dirname "$0")/.."
SAIDA="$PWD/dist-ci"
mkdir -p "$SAIDA"
ci/definir_versao.sh "$VERSAO"

python3 -m venv .venv-ci
. .venv-ci/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements-dev.txt

echo "::group::Testes"
QT_QPA_PLATFORM=offscreen python -m pytest -q tests
echo "::endgroup::"

echo "::group::PyInstaller (Linux)"
pyinstaller ExtratorLattes.spec --noconfirm --clean --distpath build-ci/linux/dist --workpath build-ci/linux/work
echo "::endgroup::"

echo "::group::Teste do executável Linux"
EXE=build-ci/linux/dist/ExtratorLattes/ExtratorLattes
"$EXE" --cli template build-ci/linux/template.xlsx
test -s build-ci/linux/template.xlsx
# o visualizador do currículo (QtWebEngine) precisa abrir dentro do executável congelado
"$EXE" --cli autoteste-visualizador tests/fixtures/1234567890123456.html build-ci/linux/visualizador.png | tee build-ci/linux/visualizador.txt
grep -q "modo=web carregou=\[True\]" build-ci/linux/visualizador.txt
echo "::endgroup::"

tar -C build-ci/linux/dist -czf "$SAIDA/ExtratorLattes-${VERSAO}-linux-x64.tar.gz" ExtratorLattes
cp build-ci/linux/visualizador.png "$SAIDA/teste-visualizador-linux.png"
du -h "$SAIDA"/*

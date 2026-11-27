#!/usr/bin/env bash
# Executável Windows (ExtratorLattes.exe). Uso: ci/build_windows.sh <versão>  (gera dist-ci/*.zip)
#   - num runner Windows (GitHub): Python Windows nativo;
#   - no runner próprio (Linux): Python Windows dentro do Wine (imagem deploy/ci-runner).
set -euo pipefail
VERSAO="${1:?versão}"
cd "$(dirname "$0")/.."
SAIDA="$PWD/dist-ci"
mkdir -p "$SAIDA"
ci/definir_versao.sh "$VERSAO"

if [[ "${RUNNER_OS:-}" == "Windows" || "${OSTYPE:-}" == msys* || "${OSTYPE:-}" == cygwin* ]]; then
  NATIVO=1
  PY=(python)
  RODAR=()
else
  NATIVO=0
  : "${PYTHON_WIN:=/opt/winpython/python.exe}"
  PY=(wine "$PYTHON_WIN")
  RODAR=(wine)
  wineboot -i >/dev/null 2>&1 || true
  [ -n "${PIP_CACHE_DIR_WIN:-}" ] && export PIP_CACHE_DIR="$PIP_CACHE_DIR_WIN"
fi

echo "::group::Dependências (Python Windows)"
"${PY[@]}" --version
"${PY[@]}" -m pip install -q --upgrade pip
"${PY[@]}" -m pip install -q --no-warn-script-location -r requirements-dev.txt
echo "::endgroup::"

echo "::group::PyInstaller (Windows)"
"${PY[@]}" -m PyInstaller ExtratorLattes.spec --noconfirm --clean \
  --distpath build-ci/windows/dist --workpath build-ci/windows/work
echo "::endgroup::"

EXE=build-ci/windows/dist/ExtratorLattes/ExtratorLattes.exe
test -f "$EXE"
echo "::group::Teste do .exe"
# Gera o template pela linha de comando do próprio .exe: prova que o executável abre, encontra os
# módulos e escreve arquivos.
rm -f build-ci/windows/template.xlsx
timeout 300 "${RODAR[@]}" "$EXE" --cli template "build-ci/windows/template.xlsx" || true
test -s build-ci/windows/template.xlsx
if [ "$NATIVO" = 1 ]; then
  # Visualizador do currículo (QtWebEngine) dentro do .exe. Informativo: a máquina do CI não tem GPU.
  timeout 300 "$EXE" --cli autoteste-visualizador tests/fixtures/1234567890123456.html \
    build-ci/windows/visualizador.png > build-ci/windows/visualizador.txt 2>&1 || true
  cat build-ci/windows/visualizador.txt || true
  [ -f build-ci/windows/visualizador.png ] && cp build-ci/windows/visualizador.png "$SAIDA/teste-visualizador-windows.png"
else
  wineserver -k 2>/dev/null || true
fi
echo "::endgroup::"

ZIP="$SAIDA/ExtratorLattes-${VERSAO}-windows-x64.zip"
rm -f "$ZIP"
if command -v 7z >/dev/null; then
  (cd build-ci/windows/dist && 7z a -tzip -mx=9 "$ZIP" ExtratorLattes >/dev/null)
else
  (cd build-ci/windows/dist && zip -qr9 "$ZIP" ExtratorLattes)
fi
ls -la "$SAIDA"

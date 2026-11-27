#!/usr/bin/env bash
# Executável Windows (ExtratorLattes.exe), num runner Windows. Uso: ci/build_windows.sh <versão>
# (gera dist-ci/*.zip). Precisa de um Python Windows: o PySide6 atual não carrega no Wine.
set -euo pipefail
VERSAO="${1:?versão}"
cd "$(dirname "$0")/.."
SAIDA="$PWD/dist-ci"
mkdir -p "$SAIDA"
ci/definir_versao.sh "$VERSAO"

if [[ "${RUNNER_OS:-}" != "Windows" && "${OSTYPE:-}" != msys* && "${OSTYPE:-}" != cygwin* ]]; then
  echo "::error::ci/build_windows.sh precisa rodar no Windows (o .exe não sai do Wine)." >&2
  exit 1
fi
PY=(python)

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
timeout 300 "$EXE" --cli template "build-ci/windows/template.xlsx" || true
test -s build-ci/windows/template.xlsx
# Verificação do ambiente dentro do .exe (bibliotecas carregadas sob demanda, Selenium Manager,
# SQLite FTS5…). O .exe não tem console: o resultado vem pelo JSON.
rm -f build-ci/windows/diagnostico.json
timeout 300 "$EXE" --cli diagnostico --sem-rede --json build-ci/windows/diagnostico.json || true
"${PY[@]}" - build-ci/windows/diagnostico.json <<'PYEOF'
import json, sys
dados = json.load(open(sys.argv[1], encoding="utf-8"))
for c in dados["checagens"]:
    print(f"[{c['status']:>5}] {c['nome']}: {c['detalhe']}")
    if c["status"] == "erro":
        print(f"::error::{c['nome']}: {c['detalhe']}")
sys.exit(0 if dados["ok"] else 1)
PYEOF
# Visualizador do currículo (QtWebEngine) dentro do .exe. Informativo: a máquina do CI não tem GPU.
timeout 300 "$EXE" --cli autoteste-visualizador tests/fixtures/1234567890123456.html \
  build-ci/windows/visualizador.png > build-ci/windows/visualizador.txt 2>&1 || true
cat build-ci/windows/visualizador.txt || true
[ -f build-ci/windows/visualizador.png ] && cp build-ci/windows/visualizador.png "$SAIDA/teste-visualizador-windows.png"
echo "::endgroup::"

ZIP="$SAIDA/ExtratorLattes-${VERSAO}-windows-x64.zip"
rm -f "$ZIP"
if command -v 7z >/dev/null; then
  (cd build-ci/windows/dist && 7z a -tzip -mx=9 "$ZIP" ExtratorLattes >/dev/null)
else
  (cd build-ci/windows/dist && zip -qr9 "$ZIP" ExtratorLattes)
fi

# Instalador (Inno Setup, já vem no runner windows-2022): um único ExtratorLattes-<versão>-setup.exe
# que instala por usuário em %LOCALAPPDATA%\Programs\ExtratorLattes, sem administrador.
echo "::group::Instalador (Inno Setup)"
ISCC="$(command -v iscc || command -v ISCC || true)"
for c in "/c/Program Files (x86)/Inno Setup 6/ISCC.exe" "/c/Program Files/Inno Setup 6/ISCC.exe"; do
  [[ -n "$ISCC" ]] && break
  [[ -x "$c" ]] && ISCC="$c"
done
[[ -n "$ISCC" ]] || { echo "::error::Inno Setup (iscc) não encontrado." >&2; exit 1; }
# Propriedades do arquivo pedem versão numérica de 4 partes: 2.1.0-dev.abc1234 -> 2.1.0.0
VERSAO_NUM="$(echo "$VERSAO" | grep -oE '^[0-9]+\.[0-9]+\.[0-9]+').0"
SETUP="$SAIDA/ExtratorLattes-${VERSAO}-setup.exe"
rm -f "$SETUP"
# Opções com "-" (não "/"): o bash do Git converteria "/D..." em caminho.
"$ISCC" -Q "-DVersao=$VERSAO" "-DVersaoNum=$VERSAO_NUM" \
  "-DOrigem=$(cygpath -w "$PWD/build-ci/windows/dist/ExtratorLattes")" \
  "-O$(cygpath -w "$SAIDA")" "$(cygpath -w "$PWD/ci/ExtratorLattes.iss")"
test -s "$SETUP"
echo "::endgroup::"
ls -la "$SAIDA"

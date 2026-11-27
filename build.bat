@echo off
REM Gera o executavel para Windows em dist\ExtratorLattes\ExtratorLattes.exe
REM Requer Python 3.10+ instalado (python.org) e o Google Chrome.
cd /d "%~dp0"
if not exist .venv ( python -m venv .venv )
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
python -m pytest -q tests || goto :erro
pyinstaller ExtratorLattes.spec --noconfirm --clean || goto :erro
REM Confere o executavel gerado (modulos, Selenium Manager, arquivos). O .exe nao tem console:
REM "start /wait" espera ele terminar e o resultado vem pelo JSON.
start "" /wait dist\ExtratorLattes\ExtratorLattes.exe --cli diagnostico --sem-rede --json dist\diagnostico.json
python -c "import json,sys; d=json.load(open(r'dist\diagnostico.json',encoding='utf-8')); [print(c['status'], c['nome'], c['detalhe']) for c in d['checagens']]; sys.exit(0 if d['ok'] else 1)" || goto :erro
echo.
echo Pronto: dist\ExtratorLattes\ExtratorLattes.exe
exit /b 0
:erro
echo Falhou. Veja as mensagens acima.
exit /b 1

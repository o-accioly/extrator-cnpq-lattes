# CLAUDE.md — Extrator CNPq Lattes

Programa desktop (PySide6) que coleta currículos da Plataforma Lattes pela busca do CNPq, encontra perfis a partir de uma planilha de nomes (com desempate de homônimos), mantém uma base pesquisável dos currículos baixados e gera planilhas Excel. Visão geral e estrutura: [`README.md`](README.md). CI, executáveis e release: [`docs/ci.md`](docs/ci.md).

Regras de processo ficam em `.claude/rules/` e carregam sozinhas: git, commit/PR e memória sempre; towncrier ao tocar código ou `changelog.d/`.

## Checklist por tarefa

1. Implementar levantando hipóteses de teste durante o desenvolvimento.
2. Testes em `tests/`: caminho feliz, borda e erro externo (site do CNPq fora do ar, HTML diferente, planilha malformada). Nada de rede nos testes: usar o currículo de `tests/fixtures/`.
3. Durante a implementação, rodar `pytest` do que foi mexido (`.venv/bin/pytest tests -x -k <alvo>`). A suíte inteira roda no CI online; não repetir a suíte local como gate.
4. Mudou tela: gerar as capturas (`tools/capturas.py`) em 1000×680, 1440×900 e 1920×1080, olhar cada uma e mostrar ao usuário antes de seguir para o PR.
5. Mudou a coleta ou o parser: teste real curto contra o CNPq (poucos perfis, `limite` baixo) além dos testes com fixture.
6. Fragmento towncrier em `changelog.d/` durante a implementação.
7. Documentação (`README.md`, `docs/`) quando o comportamento visível mudar.
8. **Fechar**: `/pr` para `homolog` → aguarda o CI verde → merge → ff do `homolog` local. Release é automática: PR `homolog` → `main`, e o CI publica a versão (ver `.claude/rules/commit-pr-review.md`).

## Convenções

- Núcleo em `lattes_extrator/` sem dependência de Qt; interface só em `lattes_extrator/gui/`. A interface fala com o núcleo por `Reporter`/`Controle` (`eventos.py`), nunca o contrário.
- Parser com lxml, uma passada por seção (`parser.py`). Campo novo do currículo entra em `COLUNAS_FIXAS` + `DESCRICOES` e ganha teste com a fixture.
- Acesso ao CNPq só pelo navegador real (`navegador.py`), no formulário do próprio site e no ritmo configurado. **Nunca** resolver ou contornar captcha: o programa avisa e espera a pessoa.
- Visual: tokens e escala de espaçamento de `gui/tema.py` (`ESP_*`, cores, `mistura()` para transparência — o Qt lê `#RRGGBBAA` como `#AARRGGBB`); ícones SVG de `gui/icones.py`; grades com `GradeResponsiva`; formulários com `CardForm`. Nada de cor ou espaçamento solto.
- Planilhas de saída pelo `exportar.py` (xlsxwriter em streaming); linhas grandes vão para JSONL em disco, nunca listas em memória.
- Textos da interface, commits, changelog e docs em português do Brasil.

## Comandos

O shell não persiste entre chamadas Bash: usar os binários do venv por caminho absoluto.

```bash
.venv/bin/python main.py                                   # interface
.venv/bin/python main.py --sem-intro                       # sem a abertura animada
.venv/bin/python -m lattes_extrator --help                 # linha de comando
.venv/bin/python -m lattes_extrator diagnostico            # verificação do ambiente (também roda no exe, no CI)
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q tests        # testes
QT_QPA_PLATFORM=offscreen .venv/bin/python tools/capturas.py /tmp/prints   # capturas de tela
.venv/bin/pyinstaller ExtratorLattes.spec --noconfirm      # executável local
.venv/bin/towncrier build --draft --version 0.0.0          # prévia do changelog
```

## Regras críticas

- Nunca editar `CHANGELOG.md` direto; usar fragmentos towncrier (o CI monta na release).
- Nunca versionar dados de coleta (`htmls/`, planilhas geradas, `extracoes.sqlite3`, `base.sqlite3`) nem currículos reais além da fixture.
- O repositório pode ficar público: nada de nome de servidor, IP, token ou dado pessoal novo em código, docs ou capturas.
- Processo longo (build, coleta real, CI): `run_in_background: true`, saída em arquivo; nunca `sleep` em foreground nem `tail` em loop.
- Não repetir rodada que já passou: só re-rodar se um `Edit`/`Write` tocou aquele código depois da última rodada verde.
- O QtWebEngine precisa ser importado antes do `QApplication` (`gui/app.py: preparar_webengine`).
- Biblioteca nova ou import feito por `importlib`/lazy: incluir no `hiddenimports` do `ExtratorLattes.spec` e numa checagem de `diagnostico.py`; o CI roda `--cli diagnostico` dentro do executável.

## Economia de turnos

- Ações independentes no mesmo bloco de tool calls.
- Planejar o arquivo e emitir os `Edit` no mesmo turno; não reler o que já está no contexto.
- Exploração pesada vai para subagent (`Explore`).

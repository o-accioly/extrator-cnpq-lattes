Abra o PR da branch atual para `homolog`, espere o CI e faça o merge.

## Fase 1 — Pré-requisitos
1. Branch atual não pode ser `homolog` nem `main`. Working tree limpo (senão, `/commit` primeiro).
2. `git fetch origin && git rebase origin/homolog` (conflito de lógica: pare e mostre ao usuário).
3. Há fragmento novo em `changelog.d/` se o diff mexe em `lattes_extrator/` ou `main.py` (o CI barra sem ele).

## Fase 2 — Checks locais rápidos (segundos)
```bash
.venv/bin/python -m compileall -q lattes_extrator tools main.py
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q tests -x -k "<alvo do que mudou>"
.venv/bin/towncrier build --draft --version 0.0.0
git diff origin/homolog...HEAD | grep -nE '(ghp_|github_pat_|AKIA|PRIVATE KEY)' && echo "SEGREDO NO DIFF"
```
Diff com tela: confirmar que as capturas foram vistas pelo usuário (CLAUDE.md, passo 4).

## Fase 3 — PR
`git push -u origin HEAD` e `gh pr create --base homolog` com título no padrão do commit principal e corpo:
- **O que muda** (para quem usa o programa) e **como foi testado** (testes, teste real no CNPq, capturas);
- sem `Co-Authored-By` nem menção a IA.

## Fase 4 — CI e merge
1. Aguardar o CI do PR (`gh pr checks --watch`, em segundo plano). Falhou: ler o log (`gh run view --log-failed`), corrigir, `/commit`, push e voltar a aguardar. Não re-rodar o que já passou.
2. Verde e sem conflito: `gh pr merge --merge --delete-branch`.
3. `git checkout homolog && git pull --ff-only origin homolog`.
4. Mostrar o link do PR mergeado.

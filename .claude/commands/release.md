Publique uma nova versão: PR `homolog` → `main`. A release em si é feita pelo CI ao mergear.

1. `git fetch origin` e conferir que `homolog` está à frente de `main` (`git log --oneline origin/main..origin/homolog`). Nada à frente: avise e encerre.
2. Fragmentos pendentes em `changelog.d/` da `homolog` (sem o `_template.md`). Zero: avise que o merge não vai gerar versão e pergunte se segue.
3. Prévia: `towncrier build --draft --version <próxima>` com a próxima versão de `python ci/versao.py <última tag>`; mostre ao usuário a versão e o changelog e peça confirmação.
4. `gh pr create --base main --head homolog --title "release: v<próxima>"` com a prévia do changelog no corpo.
5. Aguardar o CI do PR verde e `gh pr merge --merge` (sem apagar a `homolog`).
6. Acompanhar o run do push na `main` até o job **Release** terminar; mostrar o link da Release e conferir que os dois executáveis estão anexados e que o back-merge chegou na `homolog`.

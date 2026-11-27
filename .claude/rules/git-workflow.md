# Regra — Git workflow

- Branch `<tipo>-<número>/<descrição-curta>` (ex.: `feat-12/exportar-csv`), tipos `feat` `fix` `chore` `style` `perf` `docs` `test`, sempre a partir de `homolog` sincronizada.
- `main` = estável (cada merge com fragmentos vira release automática); `homolog` = desenvolvimento ativo e destino padrão dos PRs.
- Use `/branch`, `/commit` e `/pr`; não rodar `git checkout -b`, `git commit` ou `gh pr create` direto.

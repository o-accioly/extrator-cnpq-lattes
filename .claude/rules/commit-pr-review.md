# Regra — Commit, PR e code review

## Comandos do repo
- `/commit` — Conventional Commits em pt-BR, com fragmento towncrier por commit de mudança visível.
- `/pr` — checks locais rápidos → PR para `homolog` → aguarda o CI online verde → merge → ff do local. Detalhe: `.claude/commands/pr.md`.
- `/release` — abre o PR `homolog` → `main`; ao mergear, o CI publica a versão.

## Mensagens de commit
- `<tipo>(<escopo>): <descrição em pt-BR, minúscula, sem ponto final>`. Tipos: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`, `ci`, `build`.
- Escopos usuais: `parser`, `coleta`, `nomes`, `base`, `interface`, `planilhas`, `ci`.
- Nunca incluir `Co-Authored-By`, crédito ou menção a Claude/IA em commits ou no corpo de PRs.

## CI online, gate e merge
- O CI (`.github/workflows/ci.yml`) é o gate do merge: fragmento towncrier no PR, testes, executável Linux e `.exe` Windows (cada um testado depois de gerado).
- Com CI verde: checar mergeabilidade. Sem conflito ou conflito trivial (`changelog.d/`, imports) → resolver, push, aguardar o CI de novo e mergear (squash não: merge commit, para o towncrier e o histórico ficarem legíveis). Conflito de lógica → parar e mostrar ao usuário.
- Release: merge de `homolog` em `main` com fragmentos pendentes → o CI sobe a versão (removal = major, feature = minor, demais = patch), escreve o `CHANGELOG.md`, cria a tag, publica a Release com os executáveis e faz o back-merge em `homolog`.

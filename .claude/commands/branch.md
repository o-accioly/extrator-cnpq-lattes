Crie uma nova branch seguindo o padrão do projeto, a partir da `homolog` sincronizada.

Descrição da tarefa: $ARGUMENTS

1. `git status --porcelain`: se houver mudanças não commitadas, avise e **encerre**.
2. `git checkout homolog && git pull origin homolog`.
3. Próximo número: maior número já usado + 1:
   ```bash
   git branch -a | grep -oP '^\s*(?:remotes/origin/)?\K[a-z]+-\d+' | grep -oP '\d+' | sort -n | tail -1
   ```
4. Tipo pela tarefa: `feat` (funcionalidade), `fix` (bug), `chore` (CI, build, dependências, refatoração interna), `style` (visual sem lógica), `perf`, `docs`, `test`. Mistura: o dominante. Dúvida: pergunte.
5. Nome `<tipo>-<número>/<descricao-sem-acentos-com-hifens>` (até 50 caracteres na descrição) e `git checkout -b <nome>`.
6. Mostre o nome da branch criada.

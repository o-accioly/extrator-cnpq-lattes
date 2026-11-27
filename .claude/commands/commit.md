Analise as mudanças no stage e crie commits no padrão Conventional Commits.

1. `git diff --cached --stat` e `git diff --cached`. Stage vazio: avise e encerre.
2. Verificação pré-commit nos arquivos do stage — havendo problema, liste arquivo:linha e **não commite**:
   - token, chave, senha, IP de servidor ou dado pessoal (o repositório pode ser público);
   - código comentado ou comentário óbvio;
   - cor ou espaçamento solto na interface (usar `gui/tema.py`);
   - arquivo de dados de coleta (`htmls/`, `*.sqlite3`, planilhas geradas).
3. Separar em commits por contexto quando houver mudanças independentes.
4. **Fragmento towncrier por commit** com mudança visível: se não houver um no stage cobrindo aquele escopo, crie `changelog.d/<descricao-com-hifens>.<tipo>.md` (regras em `.claude/rules/towncrier.md`) e adicione ao stage. Commits internos (`chore`, `ci`, `test`, `refactor`) podem compartilhar um `.misc.md`.
5. Mensagem: `<tipo>(<escopo>): <descrição em pt-BR, minúscula, sem ponto final>`. Sem `Co-Authored-By` nem menção a IA. HEREDOC na mensagem.
6. Ao final, `git log --oneline -10`.

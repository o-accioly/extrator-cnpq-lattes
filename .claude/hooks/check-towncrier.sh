#!/bin/bash
# Hook Stop: mudança no programa sem fragmento towncrier bloqueia (exit 2) até o fragmento existir.
# Pular: SKIP_TOWNCRIER_CHECK=1 (refactor puro, teste, docs).
[ "${SKIP_TOWNCRIER_CHECK:-0}" = "1" ] && exit 0
cd "${CLAUDE_PROJECT_DIR:-$(pwd)}" || exit 0
MODIFICADOS=$(git status --porcelain 2>/dev/null | awk '{print $NF}')
[ -z "$MODIFICADOS" ] && exit 0
CODIGO=$(echo "$MODIFICADOS" | grep -E '^(lattes_extrator/.+\.py|main\.py)$' || true)
[ -z "$CODIGO" ] && exit 0
echo "$MODIFICADOS" | grep -qE '^changelog\.d/.+\.(feature|bugfix|improvement|removal|doc|misc)\.md$' && exit 0
cat >&2 <<MSG

=== Fragmento towncrier ausente ===
Código do programa modificado sem fragmento em changelog.d/:
$(echo "$CODIGO" | head -10 | sed 's/^/  - /')

Crie: changelog.d/<descricao-com-hifens>.<tipo>.md (feature, bugfix, improvement, removal, doc, misc)
Conteúdo: 1 frase para quem usa o programa, sem jargão. Refactor puro: .misc.md ou SKIP_TOWNCRIER_CHECK=1.
MSG
exit 2

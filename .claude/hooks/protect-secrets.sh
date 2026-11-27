#!/bin/bash
# Hook PreToolUse (Edit|Write): impede gravar token, chave ou IP de servidor no repositório,
# que pode ficar público.
ENTRADA=$(cat)
CONTEUDO=$(printf '%s' "$ENTRADA" | python3 -c 'import json,sys; d=json.load(sys.stdin).get("tool_input",{}); print(d.get("content","")+d.get("new_string",""))' 2>/dev/null)
if printf '%s' "$CONTEUDO" | grep -qE '(ghp_|github_pat_|gho_|ghs_)[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|sk-[A-Za-z0-9]{32,}'; then
  echo "Bloqueado: o conteúdo parece ter um token ou chave privada. Segredos ficam fora do repositório." >&2
  exit 2
fi
exit 0

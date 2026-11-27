---
paths:
  - "changelog.d/**"
  - "lattes_extrator/**/*.py"
  - "main.py"
---

# Regra — Towncrier (changelog)

Toda mudança no programa (`lattes_extrator/**/*.py`, `main.py`) leva um fragmento em `changelog.d/`; o hook Stop `check-towncrier.sh` e o CI (no PR) bloqueiam se faltar. Refactor/chore de infra: `.misc.md` ou `SKIP_TOWNCRIER_CHECK=1`.

- Público é quem usa o programa: uma ideia, frase curta, verbo no presente, foco no benefício. Sem nome de classe/função, jargão, caminho de arquivo, erro Python ou flag.
- Nunca inventar número de PR: sem `#123` ou link `/pull/...`.
- Arquivo: `<descrição-com-hifens>.<tipo>.md` (hífens, sem underscore, sem número de PR). Tipos: `feature` `bugfix` `improvement` `removal` `doc` `misc`.
- O tipo define a versão da release: `removal` → major, `feature` → minor, os demais → patch.

Exemplo — `changelog.d/exportar-csv-da-base.feature.md`:
> A base de currículos agora exporta a seleção atual direto para uma planilha.

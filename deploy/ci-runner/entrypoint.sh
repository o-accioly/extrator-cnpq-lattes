#!/usr/bin/env bash
# Um slot de CI do Extrator CNPq Lattes: registra um
# runner just-in-time (um job só; depois o GitHub o remove), roda esse job como `runner` e recomeça.
# Roda como root só para ler o token e preparar as pastas; o job nunca vê o token (o
# /proc/1/environ do root não é legível por `runner`, e `runner` não tem sudo).
#
# Ambiente (definido no deploy do compose, nunca no repositório):
#   GITHUB_REPOSITORY   dono/nome
#   GITHUB_RUNNER_PAT   token fine-grained, só este repositório, "Administration: read and write"
#   RUNNER_SLOT         1..N — entra no nome do runner e na pasta de trabalho
#   RUNNER_LABELS       separados por vírgula, ex.: "lattes-ci"
#
# Sem token, RUNNER_JITCONFIG (gerado à mão com `gh api .../generate-jitconfig`) roda um job só e sai
# — serve para testar a imagem antes de o token existir.
set -euo pipefail

: "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY ausente (dono/nome)}"
: "${RUNNER_SLOT:?RUNNER_SLOT ausente}"
RUNNER_LABELS="${RUNNER_LABELS:-lattes-ci}"
PREFIXO="lattes-slot${RUNNER_SLOT}-"

API="https://api.github.com/repos/${GITHUB_REPOSITORY}/actions/runners"
WORK_ROOT=/home/runner/_work
CACHE_ROOT=/home/runner/cache

# Volumes e tmpfs nascem do root; o job roda como `runner`. Num restart do container, um job
# anterior pode ter trocado uma dessas pastas por symlink: o `install` do root seguiria o link e
# daria a `runner` a posse do alvo. Symlink aqui é apagado antes.
for dir in "$WORK_ROOT" "$CACHE_ROOT" /home/runner/.cache; do
  [ -L "$dir" ] && rm -f "$dir"
done
install -d -o runner -g docker "$WORK_ROOT" "$CACHE_ROOT" /home/runner/.cache

job_env=(
  HOME=/home/runner
  PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
  LANG=pt_BR.UTF-8
  LC_ALL=pt_BR.UTF-8
  ImageOS=ubuntu24
  RUNNER_MANUALLY_TRAP_SIG=1
  ACTIONS_RUNNER_PRINT_LOG_TO_STDOUT=1
  RUNNER_SLOT="$RUNNER_SLOT"
  # Caches entre jobs (pip Linux e pip do Python Windows no Wine)
  PIP_CACHE_DIR="$CACHE_ROOT/pip"
  PIP_CACHE_DIR_WIN="Z:${CACHE_ROOT//\//\\}\\pip-win"
  # Wine e o Python Windows que gera o .exe (ver Dockerfile)
  WINEPREFIX="${WINEPREFIX:-/opt/wineprefix}"
  WINEARCH=win64
  WINEDEBUG=-all
  "WINEDLLOVERRIDES=mscoree,mshtml="
  PYTHON_WIN="${PYTHON_WIN:-/opt/winpython/python.exe}"
  # Qt sem tela (testes e capturas)
  QT_QPA_PLATFORM=offscreen
  "QTWEBENGINE_CHROMIUM_FLAGS=--disable-gpu --no-sandbox"
)

run_job() {  # jitconfig
  setpriv --reuid=runner --regid=docker --init-groups --inh-caps=-all --bounding-set=-all \
    env -i "${job_env[@]}" /home/runner/run.sh --jitconfig "$1"
}

if [ -n "${RUNNER_JITCONFIG:-}" ]; then
  jit="$RUNNER_JITCONFIG"
  unset RUNNER_JITCONFIG
  run_job "$jit"
  exit $?
fi

: "${GITHUB_RUNNER_PAT:?GITHUB_RUNNER_PAT ausente}"

github() {  # método, sufixo do caminho, [corpo json]
  # O token vai por um config do curl num pipe, nunca no argv: o argv aparece no `ps`.
  # O corpo precisa do content type JSON: com o padrão de formulário do curl, o generate-jitconfig
  # fica pendurado até o GitHub derrubar a conexão.
  local body=()
  [ $# -ge 3 ] && body=(-H "Content-Type: application/json" --data-binary "$3")
  curl -fsS --max-time 60 -X "$1" "${API}$2" \
    --config <(printf 'header = "Authorization: Bearer %s"\n' "$GITHUB_RUNNER_PAT") \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "${body[@]+"${body[@]}"}"
}

# Um runner just-in-time recebe só os labels que mandamos — nem o `self-hosted` vem sozinho.
labels_json="$(jq -cn --arg labels "$RUNNER_LABELS" \
  '["self-hosted", "linux", "x64"] + ($labels | split(",") | map(select(length > 0)))')"
runner_id=""
child=""
stopping=""

shutdown() {
  # Desregistra PRIMEIRO: um registro que fica para trás continua "online" e o GitHub pode mandar
  # um job para ele, que fica pendurado. `set +e`: o `wait` de um filho sinalizado devolve 143.
  set +e
  stopping=1
  [ -n "$runner_id" ] && github DELETE "/$runner_id" >/dev/null 2>&1
  [ -n "$child" ] && kill -TERM "$child" 2>/dev/null && wait "$child" 2>/dev/null
  exit 0
}
trap shutdown TERM INT

# Registros antigos deste slot (container morto antes de se desregistrar) saem antes de começar.
stale="$(github GET "?per_page=100" | jq -r --arg prefix "$PREFIXO" \
  '.runners[] | select((.name | startswith($prefix)) and (.busy | not)) | .id')" || stale=""
for id in $stale; do
  github DELETE "/$id" >/dev/null 2>&1 && echo "slot ${RUNNER_SLOT}: registro antigo $id removido"
done

while [ -z "$stopping" ]; do
  name="${PREFIXO}$(date +%s)"
  body="$(jq -cn --arg name "$name" --arg work "_work/slot-${RUNNER_SLOT}" --argjson labels "$labels_json" \
    '{name: $name, runner_group_id: 1, labels: $labels, work_folder: $work}')"
  if ! response="$(github POST /generate-jitconfig "$body")"; then
    echo "slot ${RUNNER_SLOT}: GitHub recusou o registro; nova tentativa em 30 s" >&2
    sleep 30 & wait $!
    continue
  fi
  runner_id="$(jq -r '.runner.id' <<<"$response")"
  jit="$(jq -r '.encoded_jit_config' <<<"$response")"
  unset response
  echo "slot ${RUNNER_SLOT}: ${name} pronto (${RUNNER_LABELS})"

  started=$SECONDS
  run_job "$jit" &
  child=$!
  unset jit
  status=0
  wait "$child" || status=$?
  child=""
  # Depois de um job o GitHub apaga o registro sozinho. Se o runner morreu sem pegar job, o
  # registro fica: apaga e espera, com espera crescente, para não gastar a cota de API do token.
  if [ -z "$stopping" ] && { [ "$status" -ne 0 ] || [ $((SECONDS - started)) -lt 20 ]; }; then
    github DELETE "/$runner_id" >/dev/null 2>&1 || true
    failures=$((${failures:-0} + 1))
    delay=$((30 * (1 << (failures < 5 ? failures - 1 : 4))))
    echo "slot ${RUNNER_SLOT}: runner saiu com status ${status} em $((SECONDS - started)) s; nova tentativa em ${delay} s" >&2
    runner_id=""
    sleep "$delay" & wait $!
    continue
  fi
  failures=0
  runner_id=""
done

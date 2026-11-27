# CI, changelog e release

## Fluxo

Igual ao dos outros projetos da equipe:

1. Trabalho numa branch `<tipo>-<n>/<descricao>` criada a partir de `homolog`.
2. PR para `homolog`. Mudança no programa precisa de um fragmento towncrier em `changelog.d/` (o CI barra sem ele).
3. Para publicar uma versão: PR `homolog` → `main`.
4. No merge em `main`, o CI faz a release sozinho:
   - calcula a versão pelos fragmentos pendentes: `removal` → major, `feature` → minor, os demais → patch;
   - o towncrier escreve o `CHANGELOG.md` e apaga os fragmentos usados;
   - cria a tag `vX.Y.Z` e a Release no GitHub com o `.exe` (Windows) e o executável Linux;
   - faz o back-merge de `main` em `homolog`.

Commits seguem Conventional Commits em português (`feat(base): ...`), sem menção a IA. Regras completas em `.claude/rules/`.

## O que o CI testa ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml))

Em todo PR e em todo push em `homolog` ou `main`:

1. fragmento towncrier (em PR);
2. testes (`pytest`);
3. executável **Linux** com PyInstaller, testado: gera o template e abre o visualizador do currículo (QtWebEngine) dentro do executável;
4. executável **Windows** (`ExtratorLattes.exe`) com PyInstaller, testado: o `.exe` gera o template.

Os executáveis de cada execução ficam como artefatos por 7 dias.

## Onde roda

Por padrão, nos runners do GitHub: Ubuntu para os testes e o Linux, Windows para o `.exe`.

Também existe um runner self-hosted em [`deploy/ci-runner/`](../deploy/ci-runner) para rodar num servidor próprio. Ele:

- registra um runner *just-in-time*, que atende um job só e some;
- roda o job com um usuário sem sudo, que nunca vê o token;
- tem prioridade de CPU menor que a dos outros serviços da máquina e teto de 8 CPUs e 12 GB de RAM;
- mantém a pasta de trabalho em RAM; só o cache do pip fica em disco.

A imagem acrescenta à oficial do runner o Python 3.12, as bibliotecas do Qt/QtWebEngine, o Wine e um Python 3.12 para Windows (pacote oficial do NuGet). Nesse runner o `.exe` é gerado pelo PyInstaller rodando no Wine.

Para ligar o runner self-hosted:

1. Crie um token *fine-grained* restrito a este repositório, com a permissão **Administration: Read and write** e nada além.
2. No serviço que sobe o `deploy/ci-runner/docker-compose.yml`, defina `GITHUB_RUNNER_PAT=<token>` e faça o deploy.
3. Em *Settings → Secrets and variables → Actions → Variables*, crie `USAR_RUNNER_PROPRIO=true`. Os jobs passam a usar o label `lattes-ci`. Apagar a variável volta para os runners do GitHub.

## Rodar o build localmente (mesma imagem do runner)

```bash
docker build -f deploy/ci-runner/Dockerfile -t lattes-ci-runner .
```

```bash
docker run --rm --entrypoint bash -u runner -v "$PWD":/src -w /src lattes-ci-runner -lc 'ci/build_linux.sh local && ci/build_windows.sh local'
```

Os arquivos saem em `dist-ci/`.

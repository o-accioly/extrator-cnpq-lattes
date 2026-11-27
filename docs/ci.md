# CI: testes e executáveis

O workflow [`.github/workflows/build.yml`](../.github/workflows/build.yml) roda a cada push na `main`, em pull requests e manualmente (aba *Actions → Build → Run workflow*):

1. testes (`pytest`);
2. executável **Linux** com PyInstaller, testado (gera o template e abre o visualizador do currículo com o QtWebEngine dentro do executável);
3. executável **Windows** (`ExtratorLattes.exe`) com PyInstaller rodando num Python Windows dentro do Wine, testado (o `.exe` gera o template).

Os dois executáveis ficam como artefatos do workflow por 7 dias. Numa tag `v*` (ex.: `v2.0.0`), o workflow também cria uma **Release** com os arquivos:

```bash
git tag v2.0.0
```

```bash
git push origin v2.0.0
```

## Onde roda

Num runner self-hosted no servidor próprio (servidor próprio, painel de deploy), projeto **CI Runners**, compose **Extrator Lattes - CI**. Ele usa o arquivo `deploy/ci-runner/docker-compose.yml` deste repositório e segue o mesmo desenho dos runners do outro projeto e do outro projeto:

- runner *just-in-time*: cada registro atende um job só e some;
- o usuário `runner` não tem sudo e nunca vê o token;
- prioridade de CPU menor que a da produção (`cpu_shares: 256`), teto de 8 CPUs e 12 GB de RAM;
- pasta de trabalho em RAM; só o cache do pip fica em disco;
- rede própria `10.251.70.0/24`, fora da `rede pública do proxy`.

A imagem (`deploy/ci-runner/Dockerfile`) parte da imagem oficial do runner e acrescenta o Python 3.12 do Linux, as bibliotecas do Qt/QtWebEngine, o Wine e o Python 3.12 para Windows (pacote oficial do NuGet).

## Token do runner (uma vez)

O runner precisa de um token para se registrar no repositório:

1. GitHub → *Settings → Developer settings → Fine-grained personal access tokens → Generate new token*.
2. *Resource owner*: `oaccioly-kaya`. *Repository access*: **Only select repositories → `cnpq_lattes`**.
3. *Permissions → Repository permissions → Administration: Read and write* (nada além disso).
4. No painel de deploy (servidor próprio), compose **Extrator Lattes - CI** → *Environment*: `GITHUB_RUNNER_PAT=<token>` → *Save* → *Deploy*.

Com o runner no ar, ele aparece em *Settings → Actions → Runners* do repositório como `lattes-slot1-…` sempre que estiver esperando um job.

## Rodar o build localmente (mesma imagem)

```bash
docker build -f deploy/ci-runner/Dockerfile -t lattes-ci-runner .
```

```bash
docker run --rm --entrypoint bash -u runner -v "$PWD":/src -w /src lattes-ci-runner -lc 'ci/build_linux.sh local && ci/build_windows.sh local'
```

Os arquivos saem em `dist-ci/`.

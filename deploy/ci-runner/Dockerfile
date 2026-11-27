# Runner self-hosted do GitHub Actions do Extrator CNPq Lattes (mesmo desenho dos runners do
# outros projetos no servidor próprio: imagem oficial do runner, job just-in-time, usuário sem sudo).
#
# O que esta imagem traz além da oficial:
#   - Python 3.12 do Ubuntu + bibliotecas de sistema do Qt/QtWebEngine: testes e build Linux;
#   - Wine + Python 3.12 para Windows (pacote "python" do NuGet, um zip, sem instalador): o
#     PyInstaller rodando dentro do Wine gera o ExtratorLattes.exe de verdade (PyInstaller não
#     faz build cruzado; o .exe só sai de um Python Windows).
#
# Uma mudança na imagem oficial é de propósito: o usuário `runner` perde o sudo sem senha. O
# entrypoint roda como root só para pedir o registro de um job com o token e depois desce para
# `runner`; com sudo, qualquer job leria o token.
FROM ghcr.io/actions/actions-runner:2.338.1

USER root

ARG PYTHON_WIN_VERSION=3.12.10
ENV DEBIAN_FRONTEND=noninteractive \
    WINEPREFIX=/opt/wineprefix \
    WINEARCH=win64 \
    WINEDEBUG=-all \
    WINEDLLOVERRIDES="mscoree,mshtml=" \
    PYTHON_WIN=/opt/winpython/python.exe

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates curl jq unzip zip util-linux locales \
       python3 python3-venv python3-dev \
       wine wine64 \
       libgl1 libegl1 libopengl0 libxkbcommon0 libxkbcommon-x11-0 libfontconfig1 libfreetype6 libdbus-1-3 \
       libnss3 libnspr4 libxcomposite1 libxdamage1 libxrandr2 libxtst6 libxshmfence1 libgbm1 libasound2t64 \
       libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 \
       libxcb-shape0 libxcb-xinerama0 libxcb-xkb1 libxkbfile1 fonts-dejavu-core \
    && sed -i '/pt_BR.UTF-8/s/^# //g' /etc/locale.gen && locale-gen pt_BR.UTF-8 \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /etc/sudoers.d/* \
    && printf 'Defaults env_reset\nroot ALL=(ALL:ALL) ALL\n' > /etc/sudoers \
    && gpasswd -d runner sudo

# Python Windows: o pacote "python" do NuGet é o CPython oficial empacotado como zip (pasta tools/),
# com pip. Evita o instalador .exe, que é frágil no Wine. O prefixo do Wine pertence a `runner`
# porque os jobs instalam os requirements nele.
RUN mkdir -p /opt/winpython "$WINEPREFIX" \
    && curl -fsSL -o /tmp/python.nupkg "https://www.nuget.org/api/v2/package/python/${PYTHON_WIN_VERSION}" \
    && unzip -q /tmp/python.nupkg 'tools/*' -d /tmp/py \
    && cp -r /tmp/py/tools/. /opt/winpython/ \
    && rm -rf /tmp/py /tmp/python.nupkg \
    && chown -R runner:docker /opt/winpython "$WINEPREFIX" \
    && su runner -s /bin/bash -c "export WINEPREFIX=$WINEPREFIX WINEARCH=win64 WINEDEBUG=-all WINEDLLOVERRIDES='mscoree,mshtml='; \
         wineboot -i && wineserver -w && wine $PYTHON_WIN -m pip install --no-warn-script-location -q --upgrade pip \
         && wine $PYTHON_WIN --version && wineserver -k || true" \
    && wine --version

COPY deploy/ci-runner/entrypoint.sh /usr/local/bin/ci-runner-entrypoint
RUN chmod 0755 /usr/local/bin/ci-runner-entrypoint

ENTRYPOINT ["/usr/local/bin/ci-runner-entrypoint"]

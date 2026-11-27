# Runner self-hosted do GitHub Actions do Extrator CNPq Lattes (docs/ci.md): imagem oficial do
# runner, job just-in-time, usuário sem sudo.
#
# O que esta imagem traz além da oficial: Python 3.12 do Ubuntu e as bibliotecas de sistema do
# Qt/QtWebEngine, para os testes e o executável Linux. O .exe do Windows é gerado num runner
# Windows do GitHub: o PySide6 6.12 não carrega no Wine 9 (testado com Python 3.11/3.12 e vcrun2022).
#
# Uma mudança na imagem oficial é de propósito: o usuário `runner` perde o sudo sem senha. O
# entrypoint roda como root só para pedir o registro de um job com o token e depois desce para
# `runner`; com sudo, qualquer job leria o token.
FROM ghcr.io/actions/actions-runner:2.338.1

USER root

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates curl jq unzip zip util-linux locales binutils \
       python3 python3-venv python3-dev \
       libgl1 libegl1 libopengl0 libxkbcommon0 libxkbcommon-x11-0 libfontconfig1 libfreetype6 libdbus-1-3 \
       libnss3 libnspr4 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libxtst6 libxrender1 libxi6 libxext6 libx11-xcb1 libxshmfence1 libgbm1 libasound2t64 \
       libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 \
       libxcb-shape0 libxcb-xinerama0 libxcb-xkb1 libxkbfile1 fonts-dejavu-core \
    && sed -i '/pt_BR.UTF-8/s/^# //g' /etc/locale.gen && locale-gen pt_BR.UTF-8 \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /etc/sudoers.d/* \
    && printf 'Defaults env_reset\nroot ALL=(ALL:ALL) ALL\n' > /etc/sudoers \
    && gpasswd -d runner sudo

COPY deploy/ci-runner/entrypoint.sh /usr/local/bin/ci-runner-entrypoint
RUN chmod 0755 /usr/local/bin/ci-runner-entrypoint

ENTRYPOINT ["/usr/local/bin/ci-runner-entrypoint"]

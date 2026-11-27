"""Baixa do CNPq as folhas de estilo e imagens que a página do currículo usa, para o
visualizador interno mostrar o HTML igual ao site, sem internet.

Segue @import e url() dos CSS e as imagens referenciadas pelos currículos de exemplo.
Grava em lattes_extrator/data/lattes_web/ mantendo os caminhos relativos do site
(css/..., images/...), que é como os HTMLs salvos referenciam esses arquivos.

Uso:  python tools/baixar_estilo_lattes.py [curriculo.html ...]
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

BASE = "https://buscatextual.cnpq.br/buscatextual/"
RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "lattes_extrator" / "data" / "lattes_web"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"

CSS_INICIAIS = ["css/import.css", "css/impressao.css", "css/jquery.megamenu.css", "css/style_curiculo.css",
                "css/v2/espelho.css", "css/tablet-mobile.css"]
RE_URL = re.compile(r"""url\(\s*['"]?([^'")]+)['"]?\s*\)""", re.I)
RE_IMPORT = re.compile(r"""@import\s+(?:url\()?\s*['"]?([^'");]+)['"]?\s*\)?""", re.I)
RE_IMG_HTML = re.compile(r"""src=["']([^"']+\.(?:png|gif|jpe?g|svg))["']""", re.I)


def local(url: str) -> Path | None:
    p = urlparse(url)
    if p.netloc and p.netloc != "buscatextual.cnpq.br":
        return None
    caminho = p.path
    if not caminho.startswith("/buscatextual/"):
        return None
    return DESTINO / caminho[len("/buscatextual/"):]


def main() -> int:
    sess = requests.Session()
    sess.headers["User-Agent"] = UA
    fila = [urljoin(BASE, c) for c in CSS_INICIAIS]
    for html in sys.argv[1:] or [str(RAIZ / "tests" / "fixtures" / "1234567890123456.html")]:
        texto = Path(html).read_text(encoding="utf-8", errors="replace")
        fila += [urljoin(BASE, s) for s in set(RE_IMG_HTML.findall(texto))]
    vistos: set[str] = set()
    baixados = falhas = 0
    while fila:
        url = fila.pop(0).split("#")[0].split("?")[0]
        if url in vistos:
            continue
        vistos.add(url)
        dest = local(url)
        if dest is None:
            continue
        try:
            r = sess.get(url, timeout=30)
        except requests.RequestException as e:
            print(f"  falhou {url}: {e}")
            falhas += 1
            continue
        if r.status_code != 200:
            print(f"  {r.status_code} {url}")
            falhas += 1
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(r.content)
        baixados += 1
        if url.endswith(".css"):
            css = r.content.decode("utf-8", errors="replace")
            for ref in RE_IMPORT.findall(css) + RE_URL.findall(css):
                if not ref.startswith("data:"):
                    fila.append(urljoin(url, ref.strip()))
        time.sleep(0.15)
    print(f"{baixados} arquivos em {DESTINO} ({falhas} falhas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

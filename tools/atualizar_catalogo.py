"""Atualiza o catálogo de filtros da busca do CNPq usado pela interface.

Baixa a página de busca do buscatextual, lê as opções de cada filtro e percorre a
árvore de áreas de atuação (grande área > área > subárea > especialidade) pelos
mesmos endpoints AJAX que a própria página usa. Grava o resultado em
lattes_extrator/data/catalogo_filtros.json.

Uso:  python tools/atualizar_catalogo.py [--atraso 0.4]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import lxml.html
import requests

BASE = "https://buscatextual.cnpq.br/buscatextual/"
DESTINO = Path(__file__).resolve().parent.parent / "lattes_extrator" / "data" / "catalogo_filtros.json"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"

SELECTS = {
    "paisNascimento": "paisNascimento",
    "quantidadeRegistros": "quantidadeRegistros",
    "filtros.modalidadeBolsa": "modalidadeBolsa",
    "filtros.nivelFormacao": "nivelFormacao",
    "filtros.paisFormacao": "paises",
    "filtros.regiaoFormacao": "regioes",
    "filtros.ufFormacao": "ufs",
    "filtros.codigoGrandeAreaAtuacao": "grandesAreas",
    "filtros.idioma": "idiomas",
    "filtros.setorProducao": "setoresProducao",
    "filtros.naturezaAtividade": "naturezaAtividade",
}

CHECKS = {
    "categoriaNivelBolsa": ["1A", "1B", "1C", "1D", "2", "A", "B", "C"],
    "conceitoCurso": ["1", "2", "3", "4", "5", "6", "7"],
    "orientadorCNPq": {
        "IC": "Iniciação Científica",
        "IP": "Iniciação Científica - PIBIC",
        "ME": "Mestrado",
        "DA": "Doutorado Ativo",
        "DH": "Doutorado Habilitado",
    },
}


def decodificar(resp: requests.Response) -> str:
    try:
        return resp.content.decode("utf-8")
    except UnicodeDecodeError:
        return resp.content.decode("iso-8859-1")


def opcoes(doc, nome: str) -> list[dict]:
    vistos, saida = set(), []
    for o in doc.xpath(f'//select[@name="{nome}"]/option'):
        valor = (o.get("value") or "").strip()
        texto = re.sub(r"\s+", " ", o.text_content()).strip()
        if not texto or (valor, texto) in vistos or texto.lower().startswith("selecione"):
            continue
        vistos.add((valor, texto))
        saida.append({"valor": valor, "texto": texto})
    return saida


def ajax(sess: requests.Session, acao: str, codigo: str, atraso: float) -> list[dict]:
    time.sleep(atraso)
    r = sess.get(BASE + "busca.do", params={"metodo": "ajax", "acao": acao, "codigo": codigo}, timeout=30)
    r.raise_for_status()
    xml = decodificar(r)
    itens = re.findall(r"<name><!\[CDATA\[(.*?)\]\]></name><value><!\[CDATA\[(.*?)\]\]></value>", xml, re.S)
    return [{"valor": v.strip(), "texto": n.strip()} for n, v in itens if v.strip() not in ("", "0")]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--atraso", type=float, default=0.4, help="segundos entre requisições AJAX")
    args = ap.parse_args()

    sess = requests.Session()
    sess.headers["User-Agent"] = UA
    r = sess.get(BASE + "busca.do", params={"metodo": "apresentar"}, timeout=30)
    r.raise_for_status()
    doc = lxml.html.fromstring(decodificar(r))

    catalogo: dict = {"gerado_em": time.strftime("%Y-%m-%d"), "fonte": BASE + "busca.do?metodo=apresentar"}
    for nome, chave in SELECTS.items():
        catalogo[chave] = opcoes(doc, nome)
    catalogo.update(CHECKS)
    catalogo["regioesAtividade"] = catalogo["regioes"]
    catalogo["ufsAtividade"] = catalogo["ufs"]

    # Árvore de áreas de atuação
    arvore = []
    grandes = [g for g in catalogo["grandesAreas"] if g["valor"] not in ("", "0")]
    for gi, g in enumerate(grandes, 1):
        print(f"[{gi}/{len(grandes)}] {g['texto']}", flush=True)
        no_g = {**g, "filhos": []}
        for a in ajax(sess, "areas", g["valor"], args.atraso):
            no_a = {**a, "filhos": []}
            for s in ajax(sess, "subareas", a["valor"], args.atraso):
                no_s = {**s, "filhos": ajax(sess, "espec", s["valor"], args.atraso)}
                no_a["filhos"].append(no_s)
            no_g["filhos"].append(no_a)
        arvore.append(no_g)
    catalogo["areasAtuacao"] = arvore

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(json.dumps(catalogo, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Catálogo salvo em {DESTINO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

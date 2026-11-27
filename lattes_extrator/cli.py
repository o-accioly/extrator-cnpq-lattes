"""Linha de comando (alternativa à interface gráfica).

Exemplos:
    python -m lattes_extrator                      # abre a interface
    python -m lattes_extrator processar htmls/     # gera planilha dos HTMLs
    python -m lattes_extrator coletar "cannabis" --texto cannabis --limite 50
    python -m lattes_extrator nomes minha_planilha.xlsx
    python -m lattes_extrator template template.xlsx
    python -m lattes_extrator diagnostico          # confere bibliotecas, Chrome, pasta e acesso ao CNPq
    python -m lattes_extrator listar
    python -m lattes_extrator continuar <id>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from . import jobs as J
from .config import Config
from .eventos import Controle, Reporter


def _banco(cfg: Config) -> J.Banco:
    cfg.garantir_pastas()
    return J.Banco(cfg.banco)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="lattes_extrator", description="Extrator CNPq Lattes",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--versao", action="version", version=__version__)
    # --sem-intro (abre a interface sem a animação) é tratado antes do argparse
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("gui", help="abre a interface gráfica (padrão)")

    p = sub.add_parser("processar", help="gera a planilha a partir de HTMLs baixados")
    p.add_argument("pastas", nargs="+")
    p.add_argument("--saida", help="caminho base do arquivo de saída (sem extensão)")

    c = sub.add_parser("coletar", help="coleta pela busca do CNPq")
    c.add_argument("titulo")
    c.add_argument("--texto", default="", help="termo da busca")
    c.add_argument("--nome", action="store_true", help="buscar por nome em vez de assunto")
    c.add_argument("--demais", action="store_true", help="incluir demais pesquisadores")
    c.add_argument("--sem-doutores", action="store_true")
    c.add_argument("--limite", type=int, default=0)

    n = sub.add_parser("nomes", help="busca por planilha de nomes")
    n.add_argument("planilha")
    n.add_argument("--titulo")
    n.add_argument("--so-link", action="store_true", help="não baixar o currículo completo")

    t = sub.add_parser("template", help="gera o template da planilha de nomes")
    t.add_argument("destino", nargs="?", default="template busca por nomes.xlsx")

    d = sub.add_parser("diagnostico", help="verifica se o ambiente tem tudo para rodar (sai com 1 se houver problema)")
    d.add_argument("--sem-rede", action="store_true", help="não testa o acesso ao CNPq")
    d.add_argument("--json", metavar="ARQUIVO", help="grava o resultado em JSON (útil no executável sem console)")
    d.add_argument("--estrito", action="store_true", help="avisos também contam como falha")

    sub.add_parser("listar", help="lista as extrações")
    av = sub.add_parser("autoteste-visualizador", help=argparse.SUPPRESS)
    av.add_argument("html")
    av.add_argument("png")
    k = sub.add_parser("continuar", help="continua uma extração interrompida")
    k.add_argument("id")

    argv = list(sys.argv[1:] if argv is None else argv)
    sem_intro = "--sem-intro" in argv
    argv = [x for x in argv if x != "--sem-intro"]
    a = ap.parse_args(argv)
    if a.cmd in (None, "gui"):
        from .gui.app import main as gui
        return gui([sys.argv[0]] + (["--sem-intro"] if sem_intro else []))

    cfg = Config.carregar()
    rep = Reporter()
    ctl = Controle()

    if a.cmd == "autoteste-visualizador":   # diagnóstico do executável: renderiza um HTML em PNG
        from .gui.app import preparar_webengine
        preparar_webengine()
        import time as _t
        from PySide6.QtWidgets import QApplication
        app = QApplication([sys.argv[0]])
        from .gui.visualizador_cv import VisualizadorCV
        from .texto import decodificar_html
        v = VisualizadorCV()
        v.resize(1200, 900)
        v.show()
        pronto = []
        if v.web:
            v.view.loadFinished.connect(pronto.append)
        v.carregar(decodificar_html(Path(a.html).read_bytes()))
        fim = _t.time() + 40
        while v.web and not pronto and _t.time() < fim:
            app.processEvents()
            _t.sleep(0.05)
        fim = _t.time() + 2
        while _t.time() < fim:
            app.processEvents()
            _t.sleep(0.05)
        v.grab().save(a.png)
        print(f"modo={v.modo} carregou={pronto}")
        return 0

    if a.cmd == "diagnostico":
        import json
        from . import diagnostico as D
        res = D.executar(cfg, rede=not a.sem_rede)
        print(D.texto(res))
        if a.json:
            Path(a.json).write_text(json.dumps({"ok": res.ok, "checagens": [c.como_dict() for c in res.checagens]},
                                               ensure_ascii=False, indent=2), encoding="utf-8")
        return 0 if res.ok and not (a.estrito and res.avisos) else 1

    if a.cmd == "template":
        from .planilhas import gerar_template
        print(gerar_template(a.destino))
        return 0

    if a.cmd == "processar":
        from .processamento import listar_htmls, nome_saida, processar
        arqs = listar_htmls(a.pastas)
        destino = Path(a.saida) if a.saida else cfg.pasta_planilhas / nome_saida("Compilação", len(arqs))
        r = processar(arqs, destino, palavras=cfg.palavras_chave, siglas=cfg.siglas_palavra_inteira,
                      processos=cfg.num_processos(), reporter=rep, controle=ctl,
                      raiz=Path(a.pastas[0]) if len(a.pastas) == 1 else None, gerar_tsv=cfg.gerar_tsv)
        print(f"\n{r.ok} perfis em {r.segundos:.1f}s · {len(r.erros)} erros\n{r.xlsx}")
        return 0 if r.ok else 1

    banco = _banco(cfg)
    if a.cmd == "listar":
        for j in banco.listar():
            print(f"{j.id}  {j.rotulo_status:<14} {j.rotulo_tipo:<17} {j.feitos:>5}/{j.total:<5} {j.titulo}")
        return 0

    from . import busca_nomes, coleta
    from .filtros import FiltrosBusca
    if a.cmd == "coletar":
        f = FiltrosBusca(modo="nome" if a.nome else "assunto", texto=a.texto, doutores=not a.sem_doutores,
                         demais=a.demais)
        job = coleta.criar_job(banco, cfg, a.titulo, f, limite=a.limite)
        job = coleta.executar(job, banco, cfg, rep, ctl)
    elif a.cmd == "nomes":
        job = busca_nomes.criar_job(banco, cfg, a.titulo or Path(a.planilha).stem, a.planilha,
                                    FiltrosBusca(modo="nome", doutores=True, demais=True), baixar_cv=not a.so_link)
        job = busca_nomes.executar(job, banco, cfg, rep, ctl)
    elif a.cmd == "continuar":
        job = banco.obter(a.id)
        if not job:
            print("Extração não encontrada.")
            return 1
        mod = busca_nomes if job.tipo == J.TIPO_NOMES else coleta
        job = mod.executar(job, banco, cfg, rep, ctl)
    else:
        ap.print_help()
        return 2
    print(f"\n{job.rotulo_status}: {job.feitos}/{job.total} · {job.saida or job.mensagem}")
    return 0 if job.status == J.CONCLUIDO else 1


if __name__ == "__main__":
    sys.exit(main())

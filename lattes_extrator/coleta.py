"""Coleta pela busca do CNPq: aplica os filtros, percorre todas as páginas de
resultados e baixa o HTML de cada currículo. Retomável: o que já foi baixado fica
registrado no banco e é pulado."""
from __future__ import annotations

from pathlib import Path

from . import jobs as J
from .config import Config
from .eventos import Cancelado, Controle, Progresso, Reporter
from .filtros import FiltrosBusca
from .navegador import ErroNavegador, NavegadorLattes, extrair_id16
from .processamento import listar_htmls, nome_saida, processar
from .texto import slug


def categoria(filtros: FiltrosBusca) -> str:
    if filtros.doutores and filtros.demais:
        return "Doutores e demais"
    return "Demais pesquisadores" if filtros.demais else "Doutores"


def criar_job(banco: J.Banco, cfg: Config, assunto: str, filtros: FiltrosBusca, *,
              limite: int = 0, processar_ao_final: bool = True) -> J.Job:
    pasta = cfg.pasta_htmls / f"{slug(assunto)} - {categoria(filtros)}"
    params = {"assunto": assunto, "filtros": filtros.para_dict(), "limite": limite,
              "processar_ao_final": processar_ao_final, "inicio": 0}
    return banco.criar(J.TIPO_BUSCA, assunto, params, str(pasta))


def executar(job: J.Job, banco: J.Banco, cfg: Config, rep: Reporter, ctl: Controle) -> J.Job:
    p = job.params
    filtros = FiltrosBusca.de_dict(p.get("filtros"))
    limite = int(p.get("limite") or 0)
    pasta = Path(job.pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    banco.atualizar(job.id, status=J.RODANDO, mensagem="")

    feitos = banco.chaves(job.id, J.FEITO)
    existentes = {f.stem for f in pasta.glob("*.html")}
    prog = Progresso()
    status, mensagem = J.CONCLUIDO, ""
    nav = NavegadorLattes(cfg, rep, ctl)
    try:
        nav.abrir()
        rep.etapa("Buscando no CNPq")
        total = nav.buscar(filtros)
        if total == 0:
            rep.log("A busca não encontrou nenhum currículo com esses filtros.", "aviso")
            banco.atualizar(job.id, status=J.CONCLUIDO, total=0, mensagem="Nenhum resultado")
            return banco.obter(job.id)
        alvo = min(total, limite) if limite else total
        prog.total = alvo
        prog.feitos = min(len(feitos), alvo)
        banco.atualizar(job.id, total=alvo)
        rep.log(f"{total:,} currículos encontrados".replace(",", ".") +
                (f"; coletando os primeiros {alvo}." if limite and limite < total else "."), "ok")

        # Retomada: pula direto para a página onde parou
        inicio = int(p.get("inicio") or 0)
        if inicio and inicio < total:
            rep.log(f"Retomando a partir do resultado {inicio + 1}.")
            nav.inicio_pagina = inicio - nav.por_pagina
            nav.proxima_pagina(total)

        tentativas_bloqueio = 0
        while True:
            ctl.checar()
            pagina = nav.inicio_pagina // nav.por_pagina + 1
            cands = nav.candidatos_da_pagina()
            if not cands:
                if tentativas_bloqueio >= 3:
                    raise ErroNavegador("A listagem continua vazia; o CNPq pode estar bloqueando o acesso.")
                tentativas_bloqueio += 1
                rep.log(f"Página {pagina} veio vazia (possível bloqueio). Esperando {cfg.espera_bloqueio}s…", "aviso")
                nav.aguardar_captcha("listagem")
                ctl.dormir(cfg.espera_bloqueio)
                nav.recarregar()
                continue
            tentativas_bloqueio = 0
            rep.etapa(f"Página {pagina} de {-(-total // nav.por_pagina)} · {len(cands)} perfis")
            banco.adicionar_itens(job.id, [(c.kid, {"nome": c.nome, "resumo": c.resumo}) for c in cands])

            for c in cands:
                ctl.checar()
                if limite and prog.feitos >= limite:
                    break
                if c.kid in feitos:
                    continue
                try:
                    rep.log(f"Baixando {c.nome} ({c.kid})")
                    html = nav.baixar_cv(c.kid)
                    id16 = extrair_id16(html) or c.kid
                    if id16 in existentes and id16 != c.kid:
                        rep.log(f"{c.nome}: já existia na pasta, atualizado.", "debug")
                    (pasta / f"{id16}.html").write_text(html, encoding="utf-8")
                    existentes.add(id16)
                    feitos.add(c.kid)
                    banco.marcar(job.id, c.kid, J.FEITO, id16=id16, nome=c.nome)
                    prog.avancar()
                    rep.log(f"{c.nome} → {id16}.html", "ok")
                except Cancelado:
                    raise
                except Exception as e:
                    banco.marcar(job.id, c.kid, J.FALHOU, nome=c.nome, erro=str(e))
                    prog.avancar(erro=True)
                    rep.log(f"{c.nome}: {e}", "erro")
                rep.progresso(prog, c.nome)
                banco.atualizar(job.id, feitos=prog.feitos - prog.erros, erros=prog.erros)
                nav._pausa_humana(cfg.atraso_entre_curriculos)

            if limite and prog.feitos >= limite:
                break
            banco.atualizar(job.id, params={**p, "inicio": nav.inicio_pagina + nav.por_pagina})
            if not nav.proxima_pagina(total):
                break
    except Cancelado:
        status, mensagem = J.CANCELADO, "Interrompida pelo usuário"
        rep.log("Coleta interrompida. Dá para continuar depois de onde parou.", "aviso")
    except Exception as e:
        status, mensagem = J.ERRO, str(e)
        rep.log(f"Erro na coleta: {e}", "erro")
    finally:
        nav.fechar()
        banco.recontar(job.id)
        extra = {"total": prog.total} if prog.total else {}
        banco.atualizar(job.id, status=status, mensagem=mensagem, **extra)

    if status == J.CONCLUIDO and p.get("processar_ao_final", True):
        gerar_planilha(banco.obter(job.id), banco, cfg, rep, Controle())
    return banco.obter(job.id)


def gerar_planilha(job: J.Job, banco: J.Banco, cfg: Config, rep: Reporter, ctl: Controle) -> Path | None:
    arquivos = listar_htmls([job.pasta])
    if not arquivos:
        rep.log("Nenhum currículo baixado para processar.", "aviso")
        return None
    destino = cfg.pasta_planilhas / nome_saida(slug(job.titulo), len(arquivos))
    res = processar(arquivos, destino, palavras=cfg.palavras_chave, siglas=cfg.siglas_palavra_inteira,
                    processos=cfg.num_processos(), reporter=rep, controle=ctl, raiz=cfg.pasta_htmls,
                    gerar_tsv=cfg.gerar_tsv)
    if res.xlsx:
        banco.atualizar(job.id, saida=str(res.xlsx))
    return res.xlsx

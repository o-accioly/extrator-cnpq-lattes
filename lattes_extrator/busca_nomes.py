"""Busca por nomes a partir de uma planilha.

Para cada linha: busca o nome no CNPq, separa os perfis com nome compatível e, se
houver mais de um, desempata pelos critérios das outras colunas (primeiro com os
dados leves da listagem, depois com o currículo completo dos melhores colocados).
O perfil escolhido tem o currículo baixado e extraído como numa coleta normal.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import jobs as J
from .config import Config
from .desempate import Avaliacao, avaliar, decidir, identificar_coluna, similaridade_nome
from .eventos import Cancelado, Controle, Progresso, Reporter
from .exportar import Aba
from .filtros import FiltrosBusca
from .navegador import Candidato, NavegadorLattes, extrair_id16
from .parser import parse_curriculo
from .planilhas import ler_planilha_nomes
from .processamento import nome_saida, processar
from .texto import slug

ENCONTRADO, DESEMPATADO, VERIFICAR, AMBIGUO, NAO_ENCONTRADO, FALHA = (
    "Encontrado", "Desempatado", "Verificar", "Ambíguo", "Não encontrado", "Erro")
COLUNAS_RESULTADO = ["Status", "Confiança", "Nome encontrado", "Link Lattes", "ID Lattes", "Código CNPq",
                     "Candidatos", "Motivo"]
MAX_PAGINAS_NOME = 3
CORES_STATUS = {ENCONTRADO: "#C6EFCE", DESEMPATADO: "#BDD7EE", VERIFICAR: "#FFEB9C", AMBIGUO: "#F8CBAD",
                NAO_ENCONTRADO: "#E7E6E6", FALHA: "#FFC7CE"}


def criar_job(banco: J.Banco, cfg: Config, titulo: str, planilha: str, filtros: FiltrosBusca, *,
              baixar_cv: bool = True, processar_ao_final: bool = True) -> J.Job:
    pn = ler_planilha_nomes(planilha)
    if not pn.linhas:
        raise ValueError("A planilha não tem nenhum nome preenchido.")
    pasta = cfg.pasta_htmls / f"{slug(titulo)} - Busca por nomes"
    params = {"planilha": str(planilha), "coluna_nome": pn.coluna_nome, "criterios": pn.criterios,
              "cabecalhos": pn.cabecalhos, "filtros": filtros.para_dict(), "baixar_cv": baixar_cv,
              "processar_ao_final": processar_ao_final}
    job = banco.criar(J.TIPO_NOMES, titulo, params, str(pasta))
    banco.adicionar_itens(job.id, [(f"{i:05d}", {"linha": d}) for i, d in enumerate(pn.linhas, 1)])
    banco.recontar(job.id)
    return banco.obter(job.id)


def _cand_dict(c: Candidato, av: Avaliacao | None, nome_sim: int) -> dict:
    return {"kid": c.kid, "nome": c.nome, "resumo": c.resumo, "id16": c.preview.get("id16", ""),
            "nota": round(av.nota, 3) if av else None, "nome_sim": nome_sim,
            "detalhe": av.explicar() if av else "", "completo": bool(av and av.completo)}


def resolver(nav: NavegadorLattes, cfg: Config, rep: Reporter, ctl: Controle, nome: str,
             criterios: dict[str, str], filtros: FiltrosBusca, pasta: Path, baixar_cv: bool) -> dict:
    res = {"status": NAO_ENCONTRADO, "confianca": 0.0, "nome_encontrado": "", "kid": "", "id16": "",
           "motivo": "", "candidatos": [], "arquivo": ""}

    # ID Lattes informado na planilha: confirma o perfil assim que aparecer
    alvo_id16 = ""
    for k, v in criterios.items():
        m = re.search(r"\d{16}", v)
        if m and identificar_coluna(k) == ("criterio", "id_lattes"):
            alvo_id16 = m.group(0)

    total = nav.buscar(filtros.copia(modo="nome", texto=nome))
    cands = nav.candidatos_da_pagina()
    paginas = 1
    while total > len(cands) and paginas < MAX_PAGINAS_NOME and nav.proxima_pagina(total):
        cands += nav.candidatos_da_pagina()
        paginas += 1
    if not cands:
        res["motivo"] = "a busca não retornou perfis"
        return res

    sims = {c.kid: similaridade_nome(nome, c.nome) for c in cands}
    compat = sorted((c for c in cands if sims[c.kid] >= cfg.similaridade_nome), key=lambda c: -sims[c.kid])
    # Se existe alguém com o nome exatamente igual, os aproximados (nome do meio a
    # mais etc.) saem da disputa: nomes comuns trariam centenas de "parecidos".
    exatos = [c for c in compat if sims[c.kid] >= 100]
    if exatos:
        compat = exatos
    if not compat:
        perto = sorted(cands, key=lambda c: -sims[c.kid])[:5]
        res["candidatos"] = [_cand_dict(c, None, sims[c.kid]) for c in perto]
        res["motivo"] = f"{total} resultados, nenhum com nome parecido o bastante"
        return res
    rep.log(f"{nome}: {len(compat)} perfil(is) com nome compatível" + (f" (de {total} resultados)" if total > len(compat) else ""))

    escolhido: Candidato | None = None
    avals: dict[str, Avaliacao] = {}
    htmls: dict[str, str] = {}
    usar_leve = bool(criterios)

    if usar_leve and len(compat) > 1:
        for c in compat[:30]:
            ctl.checar()
            try:
                c.preview = nav.preview(c.kid)
            except Exception as e:
                rep.log(f"Detalhes de {c.nome} indisponíveis: {e}", "debug")
            avals[c.kid] = avaliar(criterios, None, c.texto_leve(), c.preview.get("id16", ""))
            if alvo_id16 and c.preview.get("id16") == alvo_id16:
                escolhido = c
                res["motivo"] = "ID Lattes confere"
                break

    if len(compat) == 1 and not escolhido:
        escolhido = compat[0]
        if criterios:
            res["motivo"] = "único perfil com esse nome"
        else:
            res["motivo"] = "único perfil com esse nome (sem critérios)"
    elif not escolhido and not criterios:
        res["status"] = AMBIGUO
        res["motivo"] = f"{len(compat)} perfis com esse nome e nenhum critério de desempate na planilha"
    elif not escolhido:
        vencedor, motivo = decidir([(c, avals[c.kid]) for c in compat if c.kid in avals],
                                   cfg.nota_minima, cfg.margem_desempate)
        if vencedor is not None:
            escolhido, res["motivo"] = vencedor, f"pelo resumo: {motivo}"
        elif cfg.max_candidatos_cv > 0:
            topo = sorted(compat, key=lambda c: -(avals.get(c.kid).nota if c.kid in avals else 0))[:cfg.max_candidatos_cv]
            rep.log(f"{nome}: empate pelo resumo; abrindo o currículo completo de {len(topo)} candidatos")
            completos = []
            for c in topo:
                ctl.checar()
                try:
                    html = nav.baixar_cv(c.kid)
                    htmls[c.kid] = html
                    cv = parse_curriculo(html)
                    avals[c.kid] = avaliar(criterios, cv.como_linha(), "", cv.id_lattes)
                    completos.append((c, avals[c.kid]))
                except Cancelado:
                    raise
                except Exception as e:
                    rep.log(f"Currículo de {c.nome} não abriu: {e}", "aviso")
                nav._pausa_humana(cfg.atraso_entre_curriculos)
            vencedor, motivo = decidir(completos, cfg.nota_minima, cfg.margem_desempate)
            if vencedor is not None:
                escolhido, res["motivo"] = vencedor, f"pelo currículo completo: {motivo}"
            else:
                res["status"], res["motivo"] = AMBIGUO, motivo
        else:
            res["status"], res["motivo"] = AMBIGUO, motivo

    # Avaliados primeiro (completo > leve), por nota; depois os demais por semelhança do nome
    def ordem(c: Candidato):
        av = avals.get(c.kid)
        return (0 if av and av.completo else 1 if av else 2, -(av.nota if av else 0), -sims[c.kid])
    res["candidatos"] = [_cand_dict(c, avals.get(c.kid), sims[c.kid]) for c in sorted(compat, key=ordem)]
    if len(compat) > 30 and criterios:
        res["motivo"] += f" (comparados os 30 nomes mais parecidos de {len(compat)})"
    if escolhido is None:
        return res

    # Perfil escolhido: baixa (ou reaproveita) o currículo completo
    res.update(nome_encontrado=escolhido.nome, kid=escolhido.kid, id16=escolhido.preview.get("id16", ""))
    if baixar_cv:
        html = htmls.get(escolhido.kid)
        if html is None:
            html = nav.baixar_cv(escolhido.kid)
            nav._pausa_humana(cfg.atraso_entre_curriculos)
        id16 = extrair_id16(html) or escolhido.kid
        arq = pasta / f"{id16}.html"
        arq.write_text(html, encoding="utf-8")
        res.update(id16=id16, arquivo=str(arq))
        # Confere os critérios no currículo completo (dá a confiança final)
        if criterios and not (escolhido.kid in avals and avals[escolhido.kid].completo):
            cv = parse_curriculo(html)
            avals[escolhido.kid] = avaliar(criterios, cv.como_linha(), "", cv.id_lattes)

    av = avals.get(escolhido.kid)
    if criterios and av is not None:
        res["confianca"] = round(av.nota, 3)
        confere = av.nota >= cfg.nota_minima or not av.detalhes
        if not confere:
            # O currículo completo não confirma os critérios: alguém precisa olhar
            res["status"] = VERIFICAR
            res["motivo"] = (("único perfil com o nome" if len(compat) == 1 else res["motivo"])
                             + f", mas no currículo completo os critérios não conferem ({av.explicar()})")
        else:
            res["status"] = ENCONTRADO if len(compat) == 1 else DESEMPATADO
            res["motivo"] += f" · {av.explicar()}" if av.detalhes else ""
    else:
        res["confianca"] = round(sims[escolhido.kid] / 100, 3)
        res["status"] = ENCONTRADO
    return res


def executar(job: J.Job, banco: J.Banco, cfg: Config, rep: Reporter, ctl: Controle) -> J.Job:
    p = job.params
    filtros = FiltrosBusca.de_dict(p.get("filtros"))
    pasta = Path(job.pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    banco.atualizar(job.id, status=J.RODANDO, mensagem="")
    itens = list(banco.itens(job.id))
    prog = Progresso(total=len(itens), feitos=sum(1 for _, s, _ in itens if s == J.FEITO))
    status, mensagem = J.CONCLUIDO, ""
    nav = NavegadorLattes(cfg, rep, ctl)
    try:
        nav.abrir()
        for chave, st, info in itens:
            if st == J.FEITO:
                continue
            ctl.checar()
            linha = info.get("linha", {})
            nome = linha.get(p["coluna_nome"], "").strip()
            criterios = {c: linha[c] for c in p.get("criterios", []) if linha.get(c)}
            rep.etapa(f"[{prog.feitos + 1}/{prog.total}] {nome}")
            try:
                r = resolver(nav, cfg, rep, ctl, nome, criterios, filtros, pasta, p.get("baixar_cv", True))
                banco.marcar(job.id, chave, J.FEITO, resultado=r)
                nivel = "ok" if r["status"] in (ENCONTRADO, DESEMPATADO) else "aviso"
                rep.log(f"{nome}: {r['status']}" + (f" → {r['nome_encontrado']} ({r['id16'] or r['kid']})"
                                                    if r["nome_encontrado"] else "") + f" · {r['motivo']}", nivel)
                prog.avancar()
            except Cancelado:
                raise
            except Exception as e:
                banco.marcar(job.id, chave, J.FALHOU, resultado={"status": FALHA, "motivo": str(e)})
                rep.log(f"{nome}: erro: {e}", "erro")
                prog.avancar(erro=True)
            rep.progresso(prog, nome)
            banco.recontar(job.id)
            nav._pausa_humana(cfg.atraso_entre_buscas)
    except Cancelado:
        status, mensagem = J.CANCELADO, "Interrompida pelo usuário"
        rep.log("Busca interrompida. Dá para continuar depois de onde parou.", "aviso")
    except Exception as e:
        status, mensagem = J.ERRO, str(e)
        rep.log(f"Erro na busca por nomes: {e}", "erro")
    finally:
        nav.fechar()
        banco.recontar(job.id)
        banco.atualizar(job.id, status=status, mensagem=mensagem)

    if p.get("processar_ao_final", True) and status in (J.CONCLUIDO, J.CANCELADO):
        gerar_planilha(banco.obter(job.id), banco, cfg, rep, Controle())
    return banco.obter(job.id)


def gerar_planilha(job: J.Job, banco: J.Banco, cfg: Config, rep: Reporter, ctl: Controle) -> Path | None:
    p = job.params
    cab = p.get("cabecalhos") or [p["coluna_nome"]]
    linhas_res, linhas_cand = [], []
    arquivos: list[Path] = []
    por_arquivo: dict[str, dict] = {}
    for chave, st, info in banco.itens(job.id):
        linha = dict(info.get("linha", {}))
        r = info.get("resultado")
        if not r:
            r = {"status": "Pendente", "motivo": "ainda não processada"}
        nome = linha.get(p["coluna_nome"], "")
        id16 = r.get("id16", "")
        saida = dict(linha)
        saida.update({
            "Status": r.get("status", ""), "Confiança": r.get("confianca") or None,
            "Nome encontrado": r.get("nome_encontrado", ""),
            "Link Lattes": f"http://lattes.cnpq.br/{id16}" if re.fullmatch(r"\d{16}", id16 or "") else "",
            "ID Lattes": id16, "Código CNPq": r.get("kid", ""),
            "Candidatos": len(r.get("candidatos", [])), "Motivo": r.get("motivo", ""),
        })
        linhas_res.append(saida)
        for pos, c in enumerate(r.get("candidatos", []), 1):
            linhas_cand.append({
                "Nome buscado": nome, "Posição": pos, "Escolhido": c.get("kid") == r.get("kid"),
                "Nome": c.get("nome", ""), "Código CNPq": c.get("kid", ""),
                "Link Lattes": f"http://lattes.cnpq.br/{c['id16']}" if c.get("id16") else "",
                "Nota": c.get("nota"), "Semelhança do nome": c.get("nome_sim"),
                "Critérios": c.get("detalhe", ""), "Resumo na busca": c.get("resumo", ""),
            })
        if r.get("arquivo") and Path(r["arquivo"]).exists():
            arquivos.append(Path(r["arquivo"]))
            por_arquivo[str(Path(r["arquivo"]))] = {"Nome buscado": nome, "Status da busca": r.get("status", "")}

    abas_antes = [
        Aba("Busca por nomes", cab + COLUNAS_RESULTADO, linhas_res, congelar_colunas=1,
            colunas_destaque=set(COLUNAS_RESULTADO), cores={"Status": CORES_STATUS},
            larguras={"Motivo": 70, "Candidatos": 11}),
        Aba("Candidatos", ["Nome buscado", "Posição", "Escolhido", "Nome", "Código CNPq", "Link Lattes", "Nota",
                           "Semelhança do nome", "Critérios", "Resumo na busca"], linhas_cand, congelar_colunas=1,
            larguras={"Critérios": 50, "Resumo na busca": 70, "Nota": 9, "Posição": 9, "Escolhido": 10},
            cores={"Escolhido": {"Sim": "#C6EFCE"}}),
    ]
    destino = cfg.pasta_planilhas / nome_saida(slug(job.titulo), len(linhas_res))
    res = processar(arquivos, destino, palavras=cfg.palavras_chave, siglas=cfg.siglas_palavra_inteira,
                    processos=cfg.num_processos(), reporter=rep, controle=ctl, raiz=None,
                    extras=lambda a, _l: por_arquivo.get(str(a), {}), gerar_tsv=cfg.gerar_tsv,
                    abas_antes=abas_antes, exigir_arquivos=False)
    if res.xlsx:
        banco.atualizar(job.id, saida=str(res.xlsx))
    return res.xlsx

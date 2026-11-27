"""Processa currículos HTML baixados e gera a planilha consolidada.

* Paralelo (um processo por núcleo), com janela limitada de tarefas em voo: a memória
  não cresce com o número de arquivos.
* Cada linha pronta vai direto para um JSONL em disco; Excel e TSV são escritos em
  streaming a partir dele.
"""
from __future__ import annotations

import functools
import os
import time
from collections import Counter, OrderedDict
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable

from .eventos import Cancelado, Controle, Progresso, Reporter, memoria_mb
from .exportar import Aba, ArquivoLinhas, escrever_tsv, escrever_xlsx
from .parser import COLUNAS_FIXAS, DESCRICOES, aplicar_palavras_chave, compilar_palavras, parse_curriculo

COLUNAS_INICIAIS = ["Assunto", "Tipo da pesquisa"]


@functools.lru_cache(maxsize=4)
def _padroes(palavras: tuple[str, ...], siglas: tuple[str, ...]):
    return compilar_palavras(list(palavras), list(siglas))


def assunto_e_tipo(caminho: Path, raiz: Path | None) -> tuple[str, str]:
    """Pasta "assunto - tipo" (formato do coletor) vira as duas primeiras colunas."""
    pasta = caminho.parent
    if raiz is not None and pasta.resolve() == raiz.resolve():
        return "", ""
    nome = pasta.name
    if " - " in nome:
        a, t = nome.split(" - ", 1)
        return a.strip(), t.strip()
    return nome, ""


def processar_arquivo(caminho: str, raiz: str | None, palavras: tuple[str, ...], siglas: tuple[str, ...]):
    """Executado nos processos filhos. Devolve (linha, None) ou (None, erro)."""
    p = Path(caminho)
    try:
        dados = p.read_bytes()
        cv = parse_curriculo(dados, p.stem)
        assunto, tipo = assunto_e_tipo(p, Path(raiz) if raiz else None)
        linha: OrderedDict = OrderedDict([("Assunto", assunto), ("Tipo da pesquisa", tipo)])
        linha.update(cv.como_linha())
        linha.update(aplicar_palavras_chave(cv, _padroes(palavras, siglas)))
        return linha, None
    except Exception as e:  # um arquivo ruim não derruba o lote
        return None, f"{p.name}: {type(e).__name__}: {e}"


@dataclass
class ResultadoProcessamento:
    xlsx: Path | None = None
    tsv: Path | None = None
    ok: int = 0
    erros: list[str] = field(default_factory=list)
    cortes: dict[str, int] = field(default_factory=dict)
    segundos: float = 0.0


def listar_htmls(pastas: Iterable[str | os.PathLike]) -> list[Path]:
    arquivos: list[Path] = []
    for pasta in pastas:
        p = Path(pasta)
        if p.is_file() and p.suffix.lower() in (".html", ".htm"):
            arquivos.append(p)
        elif p.is_dir():
            arquivos += sorted(x for x in p.rglob("*") if x.suffix.lower() in (".html", ".htm"))
    return list(dict.fromkeys(arquivos))


def processar(
    arquivos: list[Path],
    destino_base: Path,
    *,
    palavras: list[str],
    siglas: list[str],
    processos: int,
    reporter: Reporter,
    controle: Controle | None = None,
    raiz: Path | None = None,
    extras: Callable[[Path, dict], dict] | None = None,
    gerar_tsv: bool = True,
    abas_antes: list[Aba] | None = None,
    exigir_arquivos: bool = True,
) -> ResultadoProcessamento:
    """Processa ``arquivos`` e grava ``destino_base``.xlsx (e .txt)."""
    controle = controle or Controle()
    res = ResultadoProcessamento()
    inicio = time.monotonic()
    if not arquivos and exigir_arquivos:
        reporter.log("Nenhum currículo HTML para processar.", "aviso")
        return res

    destino_base.parent.mkdir(parents=True, exist_ok=True)
    linhas = ArquivoLinhas(destino_base.with_suffix(".parcial.jsonl"))
    prog = Progresso(total=len(arquivos))
    pal, sig = tuple(palavras), tuple(siglas)
    raiz_s = str(raiz) if raiz else None

    por_assunto: Counter = Counter()
    com_palavra: Counter = Counter()

    def receber(caminho: Path, linha, erro) -> None:
        if linha is None:
            res.erros.append(erro)
            reporter.log(erro, "erro")
            prog.avancar(erro=True)
        else:
            if extras:
                linha.update(extras(caminho, linha))
            linhas.adicionar(linha)
            res.ok += 1
            por_assunto[(linha.get("Assunto", ""), linha.get("Tipo da pesquisa", ""))] += 1
            for k, v in linha.items():
                if k.startswith("Contagem: ") and v:
                    com_palavra[k[len("Contagem: "):]] += 1
            prog.avancar()
        reporter.progresso(prog, caminho.name)

    n_proc = max(1, processos)
    if arquivos:
        reporter.etapa(f"Processando {len(arquivos)} currículos com {n_proc if len(arquivos) > 8 else 1} processo(s)")
    try:
        if len(arquivos) <= 8 or n_proc == 1:
            for a in arquivos:
                controle.checar()
                receber(a, *processar_arquivo(str(a), raiz_s, pal, sig))
        else:
            with ProcessPoolExecutor(max_workers=n_proc) as ex:
                pendentes = {}
                fila = iter(arquivos)
                janela = n_proc * 4

                def encher():
                    while len(pendentes) < janela:
                        a = next(fila, None)
                        if a is None:
                            return
                        pendentes[ex.submit(processar_arquivo, str(a), raiz_s, pal, sig)] = a

                encher()
                ultimo_log_mem = 0.0
                while pendentes:
                    if controle.cancelado:
                        for f in pendentes:
                            f.cancel()
                        raise Cancelado()
                    controle.checar()
                    prontos, _ = wait(pendentes, timeout=0.5, return_when=FIRST_COMPLETED)
                    for f in prontos:
                        a = pendentes.pop(f)
                        try:
                            receber(a, *f.result())
                        except Exception as e:  # processo filho morreu
                            receber(a, None, f"{a.name}: falha no processo ({e})")
                    encher()
                    if time.monotonic() - ultimo_log_mem > 15:
                        ultimo_log_mem = time.monotonic()
                        reporter.log(f"{prog.feitos}/{prog.total} processados · {prog.taxa_por_min:.0f}/min · "
                                     f"memória {memoria_mb():.0f} MB", "debug")

        controle.checar()
        reporter.etapa("Gerando planilhas")
        colunas = _ordenar_colunas(list(linhas.colunas))
        res.xlsx = destino_base.with_suffix(".xlsx")
        abas = list(abas_antes or [])
        if arquivos:
            abas.append(Aba("Perfis", colunas, iter(linhas), congelar_colunas=_indice(colunas, "Nome") + 1))
        abas.append(_aba_resumo(res.ok, len(res.erros), por_assunto, com_palavra))
        abas.append(_aba_dicionario(colunas))
        res.cortes = escrever_xlsx(res.xlsx, abas)
        if gerar_tsv:
            res.tsv = destino_base.with_suffix(".txt")
            escrever_tsv(res.tsv, colunas, iter(linhas))
    finally:
        linhas.apagar()
        res.segundos = time.monotonic() - inicio

    reporter.log(f"Planilha gerada: {res.xlsx}", "ok")
    if res.cortes:
        total = sum(res.cortes.values())
        reporter.log(f"{total} células passaram de 32.767 caracteres e foram cortadas no Excel "
                     f"(o .txt tem o texto completo).", "aviso")
    return res


def _indice(colunas: list[str], nome: str) -> int:
    try:
        return colunas.index(nome)
    except ValueError:
        return 0


def _ordenar_colunas(colunas: list[str]) -> list[str]:
    palavras = [c for c in colunas if c.startswith(("Contagem: ", "Ocorrências (colunas): "))]
    fixas = [c for c in COLUNAS_INICIAIS + COLUNAS_FIXAS if c in colunas]
    resto = [c for c in colunas if c not in fixas and c not in palavras]
    return fixas + resto + palavras


def _aba_resumo(ok: int, erros: int, por_assunto: Counter, com_palavra: Counter) -> Aba:
    linhas = [{"Indicador": "Currículos processados", "Valor": ok},
              {"Indicador": "Arquivos com erro", "Valor": erros},
              {"Indicador": "Gerado em", "Valor": datetime.now().strftime("%d/%m/%Y %H:%M")}]
    for (a, t), n in sorted(por_assunto.items()):
        linhas.append({"Indicador": f"Perfis em: {a or '(raiz)'}{' - ' + t if t else ''}", "Valor": n})
    for p, n in com_palavra.most_common():
        linhas.append({"Indicador": f"Perfis que citam \"{p}\"", "Valor": n})
    return Aba("Resumo", ["Indicador", "Valor"], linhas, larguras={"Indicador": 60, "Valor": 18})


def _aba_dicionario(colunas: list[str]) -> Aba:
    def desc(c: str) -> str:
        if c in DESCRICOES:
            return DESCRICOES[c]
        if c.startswith("Contagem: "):
            return f"Quantas vezes \"{c[10:]}\" aparece no texto do currículo"
        if c.startswith("Ocorrências (colunas): "):
            return f"Colunas onde \"{c[23:]}\" aparece"
        if c.startswith("Qtd. "):
            return "Quantidade de itens"
        if c == "Assunto":
            return "Assunto informado na coleta (nome da pasta)"
        if c == "Tipo da pesquisa":
            return "Base da busca (Doutores / Demais pesquisadores)"
        return "Itens da seção do currículo, separados por \" ; \""
    return Aba("Dicionário", ["Coluna", "Descrição"], ({"Coluna": c, "Descrição": desc(c)} for c in colunas),
               larguras={"Coluna": 50, "Descrição": 80})


def nome_saida(prefixo: str, n: int) -> str:
    return f"{prefixo} - {n} perfis - {datetime.now().strftime('%Y-%m-%d %H-%M-%S')}"

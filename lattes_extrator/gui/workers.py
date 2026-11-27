"""Execução das tarefas em segundo plano (QThread) e ponte de eventos para a GUI."""
from __future__ import annotations

import traceback

from PySide6.QtCore import QObject, QThread, Signal

from .. import busca_nomes, coleta
from .. import jobs as J
from ..config import Config
from ..eventos import Controle, Progresso, Reporter, ReporterArquivo, fmt_duracao, memoria_mb
from ..processamento import listar_htmls, nome_saida, processar
from ..texto import slug


class Sinais(QObject):
    log = Signal(str, str)              # mensagem, nível
    progresso = Signal(dict)            # feitos, total, erros, taxa, eta, decorrido, memória, detalhe
    etapa = Signal(str)
    aguardando = Signal(str)            # ação do usuário no Chrome (captcha)
    terminou = Signal(str)              # job_id


class ReporterQt(Reporter):
    def __init__(self, sinais: Sinais) -> None:
        self.s = sinais

    def log(self, msg: str, nivel: str = "info") -> None:
        self.s.log.emit(msg, nivel)

    def progresso(self, p: Progresso, detalhe: str = "") -> None:
        self.s.progresso.emit({
            "feitos": p.feitos, "total": p.total, "erros": p.erros, "taxa": p.taxa_por_min,
            "eta": fmt_duracao(p.eta_segundos), "decorrido": fmt_duracao(p.decorrido),
            "memoria": memoria_mb(), "detalhe": detalhe,
        })

    def etapa(self, texto: str) -> None:
        self.s.etapa.emit(texto)
        self.s.log.emit(texto, "etapa")

    def aguardando_usuario(self, motivo: str) -> None:
        self.s.aguardando.emit(motivo)
        self.s.log.emit(motivo, "aviso")


class Execucao(QThread):
    """Roda uma extração (coleta, nomes ou processamento) sem travar a interface."""

    def __init__(self, job_id: str, banco: J.Banco, cfg: Config, somente_planilha: bool = False) -> None:
        super().__init__()
        self.job_id = job_id
        self.banco = banco
        self.cfg = cfg
        self.somente_planilha = somente_planilha
        self.sinais = Sinais()
        self.controle = Controle()

    def run(self) -> None:
        job = self.banco.obter(self.job_id)
        rep_qt = ReporterQt(self.sinais)
        rep: Reporter = rep_qt
        arq_log = None
        try:
            if job and job.pasta:
                from pathlib import Path
                Path(job.pasta).mkdir(parents=True, exist_ok=True)
                arq_log = ReporterArquivo(rep_qt, Path(job.pasta) / "extracao.log")
                rep = arq_log
            if job is None:
                rep.log("Extração não encontrada.", "erro")
                return
            if self.somente_planilha:
                rep.etapa("Gerando planilha")
                mod = busca_nomes if job.tipo == J.TIPO_NOMES else coleta
                mod.gerar_planilha(job, self.banco, self.cfg, rep, self.controle)
            elif job.tipo == J.TIPO_BUSCA:
                coleta.executar(job, self.banco, self.cfg, rep, self.controle)
            elif job.tipo == J.TIPO_NOMES:
                busca_nomes.executar(job, self.banco, self.cfg, rep, self.controle)
            elif job.tipo == J.TIPO_PROCESSAR:
                self._processar(job, rep)
        except Exception as e:
            rep.log(f"Falha inesperada: {e}", "erro")
            rep.log(traceback.format_exc(), "debug")
            self.banco.atualizar(self.job_id, status=J.ERRO, mensagem=str(e))
        finally:
            if arq_log:
                arq_log.fechar()
            self.sinais.terminou.emit(self.job_id)

    def _processar(self, job: J.Job, rep: Reporter) -> None:
        from pathlib import Path
        from ..eventos import Cancelado
        self.banco.atualizar(job.id, status=J.RODANDO)
        arquivos = listar_htmls(job.params.get("pastas", []))
        self.banco.atualizar(job.id, total=len(arquivos))
        destino = self.cfg.pasta_planilhas / nome_saida(slug(job.titulo), len(arquivos))
        try:
            res = processar(arquivos, destino, palavras=job.params.get("palavras", self.cfg.palavras_chave),
                            siglas=self.cfg.siglas_palavra_inteira, processos=self.cfg.num_processos(),
                            reporter=rep, controle=self.controle, raiz=self.cfg.pasta_htmls,
                            gerar_tsv=self.cfg.gerar_tsv)
            self.banco.atualizar(job.id, status=J.CONCLUIDO, feitos=res.ok, erros=len(res.erros),
                                 saida=str(res.xlsx or ""),
                                 mensagem=f"{res.ok} perfis em {res.segundos:.0f}s")
        except Cancelado:
            self.banco.atualizar(job.id, status=J.CANCELADO, mensagem="Interrompido pelo usuário")
            rep.log("Processamento interrompido.", "aviso")
            for f in Path(destino.parent).glob(destino.name + ".parcial.jsonl"):
                f.unlink(missing_ok=True)

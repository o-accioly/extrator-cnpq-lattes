"""Canal de eventos entre as tarefas (coleta, busca, processamento) e quem as exibe
(interface gráfica ou terminal). As tarefas só falam com um ``Reporter``; a GUI liga
esses métodos a sinais Qt, a CLI imprime no terminal."""
from __future__ import annotations

import datetime as _dt
import os
import threading
import time
from dataclasses import dataclass, field


class Cancelado(Exception):
    """Levantada dentro de uma tarefa quando o usuário cancela."""


class Controle:
    """Pausa e cancelamento cooperativos: a tarefa chama ``checar()`` entre itens."""

    def __init__(self) -> None:
        self._cancelar = threading.Event()
        self._rodando = threading.Event()
        self._rodando.set()

    def cancelar(self) -> None:
        self._cancelar.set()
        self._rodando.set()

    def pausar(self) -> None:
        self._rodando.clear()

    def continuar(self) -> None:
        self._rodando.set()

    @property
    def pausado(self) -> bool:
        return not self._rodando.is_set()

    @property
    def cancelado(self) -> bool:
        return self._cancelar.is_set()

    def checar(self) -> None:
        self._rodando.wait()
        if self._cancelar.is_set():
            raise Cancelado()

    def dormir(self, segundos: float) -> None:
        """sleep interrompível por cancelamento (e que respeita pausa)."""
        fim = time.monotonic() + segundos
        while True:
            self.checar()
            resta = fim - time.monotonic()
            if resta <= 0:
                return
            self._cancelar.wait(min(resta, 0.25))


@dataclass
class Progresso:
    total: int = 0
    feitos: int = 0
    erros: int = 0
    inicio: float = field(default_factory=time.monotonic)
    _taxa: float = 0.0           # itens/s, média móvel exponencial
    _ultimo: float = field(default_factory=time.monotonic)

    def avancar(self, n: int = 1, erro: bool = False) -> None:
        agora = time.monotonic()
        dt = max(agora - self._ultimo, 1e-6)
        inst = n / dt
        self._taxa = inst if self._taxa == 0 else 0.8 * self._taxa + 0.2 * inst
        self._ultimo = agora
        self.feitos += n
        if erro:
            self.erros += n

    @property
    def taxa_por_min(self) -> float:
        decorrido = time.monotonic() - self.inicio
        if self.feitos == 0 or decorrido <= 0:
            return 0.0
        media = self.feitos / decorrido
        return 60 * (0.5 * media + 0.5 * self._taxa if self._taxa else media)

    @property
    def eta_segundos(self) -> float | None:
        if not self.total or self.feitos == 0 or self.feitos >= self.total:
            return None
        por_s = self.taxa_por_min / 60
        return (self.total - self.feitos) / por_s if por_s > 0 else None

    @property
    def decorrido(self) -> float:
        return time.monotonic() - self.inicio


def memoria_mb() -> float:
    """Memória residente do processo atual (MB)."""
    try:
        import psutil
        return psutil.Process(os.getpid()).memory_info().rss / 1_048_576
    except Exception:
        try:
            import resource
            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            return rss / 1024 if os.name != "darwin" else rss / 1_048_576
        except Exception:
            return 0.0


def fmt_duracao(seg: float | None) -> str:
    if seg is None:
        return "—"
    seg = int(seg)
    h, r = divmod(seg, 3600)
    m, s = divmod(r, 60)
    return f"{h}h{m:02d}m" if h else (f"{m}m{s:02d}s" if m else f"{s}s")


class Reporter:
    """Implementação base: guarda nada, imprime no terminal. A GUI sobrescreve."""

    def log(self, msg: str, nivel: str = "info") -> None:
        hora = _dt.datetime.now().strftime("%H:%M:%S")
        print(f"[{hora}] {nivel.upper():5} {msg}", flush=True)

    def progresso(self, p: Progresso, detalhe: str = "") -> None:
        if p.total:
            print(f"\r{p.feitos}/{p.total} ({100 * p.feitos / p.total:.0f}%) "
                  f"ETA {fmt_duracao(p.eta_segundos)} {detalhe[:40]:<40}", end="", flush=True)

    def etapa(self, texto: str) -> None:
        self.log(texto, "etapa")

    def aguardando_usuario(self, motivo: str) -> None:
        """Ex.: captcha na janela do Chrome."""
        self.log(motivo, "aviso")


class ReporterArquivo(Reporter):
    """Encaminha para outro reporter e grava o log em arquivo."""

    def __init__(self, destino: Reporter, arquivo: str | os.PathLike) -> None:
        self.destino = destino
        self.arquivo = open(arquivo, "a", encoding="utf-8")

    def log(self, msg: str, nivel: str = "info") -> None:
        self._gravar(msg, nivel)
        self.destino.log(msg, nivel)

    def progresso(self, p: Progresso, detalhe: str = "") -> None:
        self.destino.progresso(p, detalhe)

    def _gravar(self, msg: str, nivel: str) -> None:
        hora = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.arquivo.write(f"[{hora}] {nivel.upper()} {msg}\n")
        self.arquivo.flush()

    def etapa(self, texto: str) -> None:
        self._gravar(texto, "etapa")
        self.destino.etapa(texto)

    def aguardando_usuario(self, motivo: str) -> None:
        self._gravar(motivo, "aviso")
        self.destino.aguardando_usuario(motivo)

    def fechar(self) -> None:
        self.arquivo.close()

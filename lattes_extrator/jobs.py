"""Registro das extrações (SQLite): permite listar, retomar de onde parou e saber o
que cada uma já baixou. Uma extração ("job") tem itens (perfis ou linhas da planilha
de nomes), cada um com seu status."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

TIPO_BUSCA = "busca"          # coleta pela busca do CNPq (filtros)
TIPO_NOMES = "nomes"          # busca por planilha de nomes
TIPO_PROCESSAR = "processar"  # só processar HTMLs já baixados

ROTULOS_TIPO = {TIPO_BUSCA: "Coleta por busca", TIPO_NOMES: "Busca por nomes", TIPO_PROCESSAR: "Processamento"}

# status de extração
NOVO, RODANDO, PAUSADO, CONCLUIDO, ERRO, CANCELADO = "novo", "rodando", "pausado", "concluido", "erro", "cancelado"
ROTULOS_STATUS = {NOVO: "Nova", RODANDO: "Em andamento", PAUSADO: "Pausada", CONCLUIDO: "Concluída",
                  ERRO: "Com erro", CANCELADO: "Interrompida"}

# status de item
PENDENTE, FEITO, FALHOU, IGNORADO = "pendente", "feito", "falhou", "ignorado"

ESQUEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY, tipo TEXT NOT NULL, titulo TEXT NOT NULL, status TEXT NOT NULL,
    criado REAL NOT NULL, atualizado REAL NOT NULL, params TEXT NOT NULL DEFAULT '{}',
    total INTEGER NOT NULL DEFAULT 0, feitos INTEGER NOT NULL DEFAULT 0, erros INTEGER NOT NULL DEFAULT 0,
    pasta TEXT NOT NULL DEFAULT '', saida TEXT NOT NULL DEFAULT '', mensagem TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS itens (
    job_id TEXT NOT NULL, chave TEXT NOT NULL, ordem INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL, info TEXT NOT NULL DEFAULT '{}', atualizado REAL NOT NULL,
    PRIMARY KEY (job_id, chave)
);
CREATE INDEX IF NOT EXISTS itens_status ON itens(job_id, status);
"""


@dataclass
class Job:
    id: str
    tipo: str
    titulo: str
    status: str
    criado: float
    atualizado: float
    params: dict = field(default_factory=dict)
    total: int = 0
    feitos: int = 0
    erros: int = 0
    pasta: str = ""
    saida: str = ""
    mensagem: str = ""

    @property
    def rotulo_tipo(self) -> str:
        return ROTULOS_TIPO.get(self.tipo, self.tipo)

    @property
    def rotulo_status(self) -> str:
        return ROTULOS_STATUS.get(self.status, self.status)

    @property
    def fracao(self) -> float:
        return (self.feitos / self.total) if self.total else 0.0

    @property
    def pode_continuar(self) -> bool:
        return self.status in (PAUSADO, CANCELADO, ERRO, RODANDO, NOVO)


class Banco:
    """Acesso thread-safe (uma conexão, protegida por lock; volume é pequeno)."""

    def __init__(self, caminho: str | Path) -> None:
        Path(caminho).parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(str(caminho), check_same_thread=False, isolation_level=None)
        self._con.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            self._con.execute("PRAGMA journal_mode=WAL")
            self._con.executescript(ESQUEMA)
            # Extrações que estavam rodando quando o programa fechou viram "interrompidas"
            self._con.execute("UPDATE jobs SET status=? WHERE status=?", (CANCELADO, RODANDO))

    def fechar(self) -> None:
        with self._lock:
            self._con.close()

    # --- jobs ---
    def criar(self, tipo: str, titulo: str, params: dict, pasta: str = "") -> Job:
        agora = time.time()
        job = Job(uuid.uuid4().hex[:12], tipo, titulo, NOVO, agora, agora, params, pasta=pasta)
        with self._lock:
            self._con.execute(
                "INSERT INTO jobs (id,tipo,titulo,status,criado,atualizado,params,pasta) VALUES (?,?,?,?,?,?,?,?)",
                (job.id, tipo, titulo, NOVO, agora, agora, json.dumps(params, ensure_ascii=False), pasta))
        return job

    def obter(self, job_id: str) -> Job | None:
        with self._lock:
            r = self._con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return self._job(r) if r else None

    def listar(self, limite: int = 200) -> list[Job]:
        with self._lock:
            rs = self._con.execute("SELECT * FROM jobs ORDER BY atualizado DESC LIMIT ?", (limite,)).fetchall()
        return [self._job(r) for r in rs]

    def atualizar(self, job_id: str, **campos) -> None:
        if not campos:
            return
        if "params" in campos:
            campos["params"] = json.dumps(campos["params"], ensure_ascii=False)
        campos["atualizado"] = time.time()
        sets = ", ".join(f"{k}=?" for k in campos)
        with self._lock:
            self._con.execute(f"UPDATE jobs SET {sets} WHERE id=?", (*campos.values(), job_id))

    def recontar(self, job_id: str) -> tuple[int, int, int]:
        with self._lock:
            r = self._con.execute(
                "SELECT COUNT(*), SUM(status=?), SUM(status=?) FROM itens WHERE job_id=?",
                (FEITO, FALHOU, job_id)).fetchone()
        total, feitos, erros = r[0] or 0, r[1] or 0, r[2] or 0
        self.atualizar(job_id, total=total, feitos=feitos, erros=erros)
        return total, feitos, erros

    def excluir(self, job_id: str) -> None:
        with self._lock:
            self._con.execute("DELETE FROM itens WHERE job_id=?", (job_id,))
            self._con.execute("DELETE FROM jobs WHERE id=?", (job_id,))

    # --- itens ---
    def adicionar_itens(self, job_id: str, itens: list[tuple[str, dict]]) -> int:
        """Insere itens novos (ignora chaves repetidas). Devolve quantos entraram."""
        agora = time.time()
        with self._lock:
            base = self._con.execute("SELECT COALESCE(MAX(ordem),0) FROM itens WHERE job_id=?", (job_id,)).fetchone()[0]
            antes = self._con.total_changes
            self._con.executemany(
                "INSERT OR IGNORE INTO itens (job_id,chave,ordem,status,info,atualizado) VALUES (?,?,?,?,?,?)",
                [(job_id, k, base + i + 1, PENDENTE, json.dumps(info, ensure_ascii=False), agora)
                 for i, (k, info) in enumerate(itens)])
            return self._con.total_changes - antes

    def marcar(self, job_id: str, chave: str, status: str, **info) -> None:
        with self._lock:
            r = self._con.execute("SELECT info FROM itens WHERE job_id=? AND chave=?", (job_id, chave)).fetchone()
            atual = json.loads(r["info"]) if r else {}
            atual.update(info)
            self._con.execute(
                "INSERT INTO itens (job_id,chave,status,info,atualizado) VALUES (?,?,?,?,?) "
                "ON CONFLICT(job_id,chave) DO UPDATE SET status=excluded.status, info=excluded.info, atualizado=excluded.atualizado",
                (job_id, chave, status, json.dumps(atual, ensure_ascii=False), time.time()))

    def itens(self, job_id: str, status: str | None = None) -> Iterator[tuple[str, str, dict]]:
        sql = "SELECT chave,status,info FROM itens WHERE job_id=?"
        args: tuple = (job_id,)
        if status:
            sql += " AND status=?"
            args += (status,)
        with self._lock:
            rs = self._con.execute(sql + " ORDER BY ordem", args).fetchall()
        for r in rs:
            yield r["chave"], r["status"], json.loads(r["info"])

    def chaves(self, job_id: str, status: str | None = None) -> set[str]:
        return {k for k, _, _ in self.itens(job_id, status)}

    @staticmethod
    def _job(r: sqlite3.Row) -> Job:
        d = dict(r)
        d["params"] = json.loads(d.get("params") or "{}")
        return Job(**d)

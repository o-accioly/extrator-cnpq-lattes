"""Base de currículos: índice pesquisável de todos os HTMLs baixados.

* Um registro por arquivo, com os campos principais e um texto de busca.
* Busca de texto completo (SQLite FTS5, sem acento e sem diferenciar maiúsculas).
* Atualização incremental: só reprocessa arquivos novos ou alterados (pelo mtime).
* O perfil completo não fica no banco: é lido do HTML na hora (≈0,2 s), o que
  mantém o índice pequeno mesmo com milhares de currículos.
"""
from __future__ import annotations

import os
import sqlite3
import threading
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from .eventos import Controle, Progresso, Reporter
from .parser import parse_curriculo
from .texto import normalizar

CAMPOS = ["id16", "kid", "nome", "titulacao", "ano_titulacao", "inst_titulacao", "inst_atual", "areas",
          "atualizacao", "bolsa", "orcid", "artigos", "producao", "orientacoes", "citacoes_wos", "fator_h", "resumo"]

ESQUEMA = """
CREATE TABLE IF NOT EXISTS perfis (
    arquivo TEXT PRIMARY KEY, pasta TEXT NOT NULL, mtime REAL NOT NULL, tamanho INTEGER NOT NULL,
    id16 TEXT, kid TEXT, nome TEXT, titulacao TEXT, ano_titulacao TEXT, inst_titulacao TEXT, inst_atual TEXT,
    areas TEXT, atualizacao TEXT, bolsa TEXT, orcid TEXT, artigos INTEGER, producao INTEGER, orientacoes INTEGER,
    citacoes_wos INTEGER, fator_h INTEGER, resumo TEXT, nome_norm TEXT, erro TEXT
);
CREATE INDEX IF NOT EXISTS perfis_id16 ON perfis(id16);
CREATE INDEX IF NOT EXISTS perfis_nome ON perfis(nome_norm);
"""
ESQUEMA_FTS = ("CREATE VIRTUAL TABLE IF NOT EXISTS perfis_busca USING fts5("
               "arquivo UNINDEXED, nome, texto, tokenize='unicode61 remove_diacritics 2')")

ORDENS = {
    "nome": "nome_norm COLLATE NOCASE ASC",
    "atualizacao": "substr(atualizacao,7,4)||substr(atualizacao,4,2)||substr(atualizacao,1,2) DESC",
    "artigos": "artigos DESC",
    "citacoes": "citacoes_wos DESC",
    "relevancia": None,
}
LIMITE_TEXTO = 80_000  # caracteres de texto de busca por currículo


def _int(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def indexar_arquivo(caminho: str) -> tuple[str, dict | None, str]:
    """Executado em processo filho: lê o HTML e devolve (caminho, campos, texto de busca)."""
    try:
        cv = parse_curriculo(Path(caminho).read_bytes(), Path(caminho).stem)
    except Exception as e:
        return caminho, {"erro": f"{type(e).__name__}: {e}"}, ""
    c = cv.campos
    dados = {
        "id16": str(c["ID Lattes"] or ""), "kid": c["Código CNPq"], "nome": c["Nome"],
        "titulacao": c["Maior titulação"], "ano_titulacao": c["Ano da maior titulação"],
        "inst_titulacao": c["Instituição da maior titulação"], "inst_atual": c["Instituição atual"],
        "areas": c["Áreas de atuação"], "atualizacao": c["Última atualização"],
        "bolsa": c["Bolsa de produtividade"], "orcid": c["ORCID"],
        "artigos": _int(c["Qtd. artigos em periódicos"]), "producao": _int(c["Produção bibliográfica (total)"]),
        "orientacoes": _int(c["Qtd. orientações concluídas"]), "citacoes_wos": _int(c["Web of Science: citações"]),
        "fator_h": _int(c["Web of Science: fator H"]), "resumo": c["Resumo"], "erro": None,
    }
    sem_busca = {"ID Lattes", "Código CNPq", "Link Lattes", "ORCID", "Última atualização"}
    partes = [str(v) for k, v in c.items() if isinstance(v, str) and v and k not in sem_busca]
    partes += [v for v in cv.secoes.values() if v]
    texto = " \n ".join(partes)[:LIMITE_TEXTO]
    return caminho, dados, texto


@dataclass
class Resultado:
    arquivo: str
    pasta: str
    dados: dict
    outras_pastas: list[str]
    trecho: str = ""


class BaseCurriculos:
    def __init__(self, caminho_banco: str | Path) -> None:
        Path(caminho_banco).parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(str(caminho_banco), check_same_thread=False, isolation_level=None)
        self._con.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            self._con.execute("PRAGMA journal_mode=WAL")
            self._con.executescript(ESQUEMA)
            try:
                self._con.execute(ESQUEMA_FTS)
                self.fts = True
            except sqlite3.OperationalError:   # SQLite sem FTS5: busca por LIKE
                self.fts = False

    def fechar(self) -> None:
        with self._lock:
            self._con.close()

    # ------------------------------------------------------------ atualização
    def pendentes(self, raiz: Path) -> tuple[list[Path], list[str]]:
        """Arquivos novos/alterados e registros cujos arquivos sumiram."""
        no_disco = {}
        if raiz.exists():
            for p in raiz.rglob("*.html"):
                try:
                    st = p.stat()
                except OSError:
                    continue
                no_disco[str(p)] = (st.st_mtime, st.st_size)
        with self._lock:
            no_banco = {r["arquivo"]: (r["mtime"], r["tamanho"])
                        for r in self._con.execute("SELECT arquivo, mtime, tamanho FROM perfis")}
        novos = [Path(a) for a, info in no_disco.items() if no_banco.get(a) != info]
        sumiram = [a for a in no_banco if a not in no_disco]
        return sorted(novos), sumiram

    def atualizar(self, raiz: Path, *, processos: int = 1, reporter: Reporter | None = None,
                  controle: Controle | None = None) -> tuple[int, int]:
        """Indexa o que mudou em ``raiz``. Devolve (indexados, removidos)."""
        rep = reporter or Reporter()
        ctl = controle or Controle()
        novos, sumiram = self.pendentes(raiz)
        if sumiram:
            with self._lock:
                self._con.executemany("DELETE FROM perfis WHERE arquivo=?", [(a,) for a in sumiram])
                if self.fts:
                    self._con.executemany("DELETE FROM perfis_busca WHERE arquivo=?", [(a,) for a in sumiram])
        if not novos:
            return 0, len(sumiram)
        prog = Progresso(total=len(novos))
        lote: list[tuple[str, dict, str]] = []

        def gravar() -> None:
            if not lote:
                return
            with self._lock:
                self._con.execute("BEGIN")
                for caminho, dados, texto in lote:
                    p = Path(caminho)
                    st = p.stat() if p.exists() else None
                    linha = {k: dados.get(k) for k in CAMPOS}
                    self._con.execute(
                        "INSERT OR REPLACE INTO perfis (arquivo, pasta, mtime, tamanho, nome_norm, erro, "
                        + ", ".join(CAMPOS) + ") VALUES (?,?,?,?,?,?," + ",".join("?" * len(CAMPOS)) + ")",
                        (caminho, p.parent.name, st.st_mtime if st else 0, st.st_size if st else 0,
                         normalizar(dados.get("nome") or ""), dados.get("erro"), *linha.values()))
                    if self.fts:
                        self._con.execute("DELETE FROM perfis_busca WHERE arquivo=?", (caminho,))
                        self._con.execute("INSERT INTO perfis_busca (arquivo, nome, texto) VALUES (?,?,?)",
                                          (caminho, dados.get("nome") or "", texto))
                self._con.execute("COMMIT")
            lote.clear()

        if len(novos) <= 6 or processos <= 1:
            for p in novos:
                ctl.checar()
                lote.append(indexar_arquivo(str(p)))
                prog.avancar()
                rep.progresso(prog, p.name)
                if len(lote) >= 50:
                    gravar()
        else:
            with ProcessPoolExecutor(max_workers=processos) as ex:
                for r in ex.map(indexar_arquivo, [str(p) for p in novos], chunksize=8):
                    ctl.checar()
                    lote.append(r)
                    prog.avancar()
                    rep.progresso(prog, Path(r[0]).name)
                    if len(lote) >= 100:
                        gravar()
        gravar()
        return len(novos), len(sumiram)

    # ------------------------------------------------------------------ busca
    def total(self) -> int:
        with self._lock:
            return self._con.execute(
                "SELECT COUNT(DISTINCT COALESCE(NULLIF(id16,''), arquivo)) FROM perfis WHERE erro IS NULL").fetchone()[0]

    def facetas(self) -> dict[str, list[tuple[str, int]]]:
        with self._lock:
            pastas = self._con.execute("SELECT pasta, COUNT(*) n FROM perfis GROUP BY pasta ORDER BY pasta").fetchall()
            tit = self._con.execute("SELECT titulacao, COUNT(*) n FROM perfis WHERE titulacao<>'' "
                                    "GROUP BY titulacao ORDER BY n DESC").fetchall()
        return {"pastas": [(r[0], r[1]) for r in pastas], "titulacoes": [(r[0], r[1]) for r in tit]}

    @staticmethod
    def _consulta_fts(texto: str) -> str:
        """Cada palavra vira prefixo obrigatório; trechos entre aspas viram frase."""
        import re
        frases = re.findall(r'"([^"]+)"', texto)
        resto = re.sub(r'"[^"]+"', " ", texto)
        termos = [f'"{normalizar(f)}"' for f in frases if normalizar(f)]
        termos += [f'"{t}"*' for t in normalizar(resto).split() if t]
        return " AND ".join(termos)

    def buscar(self, texto: str = "", *, pasta: str = "", titulacao: str = "", ordem: str = "nome",
               limite: int = 500) -> tuple[list[Resultado], int]:
        """Resultados (um por pesquisador) e o total encontrado."""
        cond, args = ["p.erro IS NULL"], []
        rank_join = ""
        texto = texto.strip()
        if texto and self.fts:
            q = self._consulta_fts(texto)
            if q:
                rank_join = "JOIN (SELECT arquivo, bm25(perfis_busca, 0, 8.0, 1.0) AS rank, " \
                            "snippet(perfis_busca, 2, '[', ']', '…', 14) AS trecho FROM perfis_busca " \
                            "WHERE perfis_busca MATCH ?) f ON f.arquivo = p.arquivo"
                args.append(q)
        elif texto:
            cond.append("(p.nome_norm LIKE ? OR p.resumo LIKE ? OR p.areas LIKE ?)")
            args += [f"%{normalizar(texto)}%", f"%{texto}%", f"%{texto}%"]
        if pasta:
            cond.append("p.pasta = ?")
            args.append(pasta)
        if titulacao:
            cond.append("p.titulacao = ?")
            args.append(titulacao)
        ordem_sql = ORDENS.get(ordem) or ("f.rank" if rank_join else ORDENS["nome"])
        extra = ", f.trecho" if rank_join else ", '' AS trecho"
        sql = f"""
            WITH base AS (
                SELECT p.*{extra}{', f.rank' if rank_join else ''},
                       ROW_NUMBER() OVER (PARTITION BY COALESCE(NULLIF(p.id16,''), p.arquivo) ORDER BY p.mtime DESC) AS rn,
                       GROUP_CONCAT(p.pasta) OVER (PARTITION BY COALESCE(NULLIF(p.id16,''), p.arquivo)) AS todas
                FROM perfis p {rank_join}
                WHERE {' AND '.join(cond)}
            )
            SELECT *, COUNT(*) OVER () AS total FROM base WHERE rn = 1 ORDER BY {ordem_sql.replace('f.rank', 'rank')} LIMIT ?
        """
        with self._lock:
            try:
                rs = self._con.execute(sql, (*args, limite)).fetchall()
            except sqlite3.OperationalError:
                return [], 0
        saida = []
        for r in rs:
            d = {k: r[k] for k in CAMPOS}
            pastas = sorted(set((r["todas"] or "").split(",")) - {r["pasta"]})
            saida.append(Resultado(r["arquivo"], r["pasta"], d, pastas, r["trecho"] or ""))
        total = rs[0]["total"] if rs else 0
        return saida, total

    def obter(self, arquivo: str) -> dict | None:
        with self._lock:
            r = self._con.execute("SELECT * FROM perfis WHERE arquivo=?", (arquivo,)).fetchone()
        return dict(r) if r else None

    def arquivos_do(self, id16: str) -> list[str]:
        with self._lock:
            return [r[0] for r in self._con.execute("SELECT arquivo FROM perfis WHERE id16=? ORDER BY mtime DESC",
                                                    (id16,))]

    def exportar(self, arquivos: list[str]) -> list[str]:
        """Caminhos existentes (para gerar planilha de uma seleção)."""
        return [a for a in arquivos if os.path.exists(a)]


def atualizar_em_segundo_plano(base: BaseCurriculos, raiz: Path, processos: int) -> tuple[int, int, float]:
    t = time.monotonic()
    n, rem = base.atualizar(raiz, processos=processos)
    return n, rem, time.monotonic() - t

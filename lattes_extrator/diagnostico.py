"""Checagem do ambiente: confere, antes de qualquer extração, se tudo que o programa usa está
no lugar (bibliotecas, Selenium Manager, Chrome, arquivos internos, pasta de trabalho, acesso ao
CNPq). Roda ao abrir a interface, pela linha de comando (``diagnostico``) e no CI dentro do
executável gerado, para que falta de módulo no empacotamento apareça antes de chegar à pessoa.

Sem dependência de Qt; a interface acrescenta as checagens dela (QtWebEngine) por conta própria.
"""
from __future__ import annotations

import importlib
import os
import shutil
import sqlite3
import ssl
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from .config import Config

OK, AVISO, ERRO = "ok", "aviso", "erro"

# Funções do programa afetadas por cada checagem (texto que aparece para a pessoa)
COLETA = "Coletar pela busca"
NOMES = "Buscar por nomes"
PLANILHA = "Gerar planilha"
BASE = "Base de currículos"
TODAS = (COLETA, NOMES, PLANILHA, BASE)

URL_CNPQ = "https://buscatextual.cnpq.br/buscatextual/busca.do?metodo=apresentar"
ESPACO_MINIMO_MB = 1024


@dataclass
class Checagem:
    nome: str
    status: str = OK
    detalhe: str = ""
    dica: str = ""
    afeta: tuple[str, ...] = ()
    segundos: float = 0.0

    @property
    def ok(self) -> bool:
        return self.status == OK

    def como_dict(self) -> dict:
        d = asdict(self)
        d["afeta"] = list(self.afeta)
        return d


@dataclass
class Resultado:
    checagens: list[Checagem] = field(default_factory=list)

    @property
    def erros(self) -> list[Checagem]:
        return [c for c in self.checagens if c.status == ERRO]

    @property
    def avisos(self) -> list[Checagem]:
        return [c for c in self.checagens if c.status == AVISO]

    @property
    def ok(self) -> bool:
        return not self.erros

    def bloqueia(self, funcao: str) -> list[Checagem]:
        """Erros que impedem ``funcao`` (ex.: ``NOMES``) de rodar."""
        return [c for c in self.erros if funcao in c.afeta]

    def resumo(self) -> str:
        if not self.erros and not self.avisos:
            return f"Tudo pronto: {len(self.checagens)} verificações sem problema."
        partes = []
        if self.erros:
            partes.append(plural(len(self.erros), "problema", "problemas"))
        if self.avisos:
            partes.append(plural(len(self.avisos), "aviso", "avisos"))
        return " e ".join(partes).capitalize() + " no ambiente."


def plural(n: int, um: str, varios: str) -> str:
    return f"{n} {um if n == 1 else varios}"


# ----------------------------------------------------------------- checagens
def _modulos(nome: str, afeta: tuple[str, ...], dica: str, *caminhos: str) -> Callable[[], Checagem]:
    """Importa os módulos pelo caminho exato usado no programa (inclusive os que a biblioteca
    carrega sob demanda, que o empacotador não enxerga)."""
    def checar() -> Checagem:
        faltando = []
        for caminho in caminhos:
            modulo, _, atributo = caminho.partition(":")
            try:
                m = importlib.import_module(modulo)
                if atributo:
                    getattr(m, atributo)
            except Exception as e:  # ImportError, AttributeError, DLL que não carrega…
                faltando.append(f"{caminho} ({type(e).__name__}: {e})")
        if faltando:
            return Checagem(nome, ERRO, "Não carregou: " + "; ".join(faltando), dica, afeta)
        return Checagem(nome, OK, "", "", afeta)
    return checar


def checar_selenium() -> Checagem:
    afeta = (COLETA, NOMES)
    dica = ("O executável está incompleto. Baixe a versão mais recente do programa; se o erro continuar, "
            "avise quem mantém o programa.")
    c = _modulos("Automação do Chrome (Selenium)", afeta, dica,
                 "selenium.webdriver:ChromeOptions", "selenium.webdriver:Chrome",
                 "selenium.webdriver.chrome.options:Options", "selenium.webdriver.chrome.service:Service",
                 "selenium.webdriver.chrome.webdriver:WebDriver",
                 "selenium.webdriver.common.selenium_manager:SeleniumManager")()
    if not c.ok:
        return c
    try:
        from selenium.webdriver.common.selenium_manager import SeleniumManager
        binario = Path(SeleniumManager._get_binary())
    except Exception as e:
        return Checagem(c.nome, ERRO, f"Selenium Manager não encontrado: {e}", dica, afeta)
    if not binario.is_file():
        return Checagem(c.nome, ERRO, f"Selenium Manager ausente em {binario}", dica, afeta)
    if not sys.platform.startswith("win") and not os.access(binario, os.X_OK):
        return Checagem(c.nome, ERRO, f"Selenium Manager sem permissão de execução: {binario}",
                        f"Rode: chmod +x \"{binario}\"", afeta)
    import selenium
    return Checagem(c.nome, OK, f"Selenium {selenium.__version__}", "", afeta)


def checar_desempate() -> Checagem:
    """O RapidFuzz carrega o motor compilado sob demanda; sem ele o desempate cai no difflib
    (mais lento e menos preciso), então isso é aviso, não erro."""
    afeta = (NOMES,)
    try:
        from rapidfuzz import fuzz
        nota = fuzz.token_set_ratio("ana beatriz exemplo", "ana beatriz exemplo vasconcelos")
        if nota < 99:
            raise ValueError(f"resultado inesperado ({nota})")
        from rapidfuzz.distance import Levenshtein  # noqa: F401  (outro módulo carregado sob demanda)
        motor = "compilado" if "cpp" in fuzz.ratio.__module__ else "Python (mais lento)"
        return Checagem("Comparação de nomes (RapidFuzz)", OK, f"motor {motor}", "", afeta)
    except Exception as e:
        return Checagem("Comparação de nomes (RapidFuzz)", AVISO,
                        f"RapidFuzz indisponível ({type(e).__name__}: {e}); usando comparação simples.",
                        "A busca por nomes funciona, mas desempata pior e mais devagar. Atualize o programa.", afeta)


def localizar_chrome() -> str | None:
    for nome in ("google-chrome", "google-chrome-stable", "chrome", "chromium", "chromium-browser"):
        achado = shutil.which(nome)
        if achado:
            return achado
    candidatos: list[Path] = []
    if sys.platform.startswith("win"):
        for var in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            base = os.environ.get(var)
            if base:
                candidatos.append(Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe")
    elif sys.platform == "darwin":
        candidatos += [Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
                       Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
    else:
        candidatos += [Path("/opt/google/chrome/chrome"), Path("/usr/bin/google-chrome")]
    for p in candidatos:
        if p.is_file():
            return str(p)
    return None


def checar_chrome() -> Checagem:
    afeta = (COLETA, NOMES)
    achado = localizar_chrome()
    if achado:
        return Checagem("Google Chrome", OK, achado, "", afeta)
    return Checagem("Google Chrome", AVISO, "Chrome não encontrado neste computador.",
                    "Instale o Google Chrome (google.com/chrome). Sem ele, a primeira coleta tenta baixar uma "
                    "versão de teste do Chrome, o que exige internet e demora.", afeta)


def checar_arquivos_internos() -> Checagem:
    from .filtros import _pasta_dados
    dados = _pasta_dados()
    necessarios = ["catalogo_filtros.json", "ascii_accioly.txt", "icone.png", "lattes_web"]
    faltando = [n for n in necessarios if not (dados / n).exists()]
    if faltando:
        return Checagem("Arquivos do programa", ERRO, f"Faltando em {dados}: {', '.join(faltando)}",
                        "Reinstale o programa (baixe o .zip de novo e extraia tudo).", TODAS)
    try:
        from .filtros import catalogo
        catalogo()
    except Exception as e:
        return Checagem("Arquivos do programa", ERRO, f"Catálogo de filtros ilegível: {e}",
                        "Reinstale o programa.", (COLETA,))
    return Checagem("Arquivos do programa", OK, str(dados), "", TODAS)


def checar_pasta_trabalho(cfg: Config) -> Checagem:
    nome = "Pasta de trabalho"
    raiz = cfg.raiz
    try:
        cfg.garantir_pastas()
        with tempfile.NamedTemporaryFile(dir=raiz, prefix=".teste-escrita-", delete=True) as f:
            f.write(b"ok")
    except OSError as e:
        return Checagem(nome, ERRO, f"Sem permissão de escrita em {raiz}: {e}",
                        "Escolha outra pasta em Configurações > Pasta de trabalho.", TODAS)
    livre_mb = shutil.disk_usage(raiz).free / 2**20
    nuvem = [p for p in ("OneDrive", "Dropbox", "Google Drive", "GoogleDrive", "iCloud") if p.lower() in str(raiz).lower()]
    if livre_mb < ESPACO_MINIMO_MB:
        return Checagem(nome, AVISO, f"{raiz} — só {livre_mb:,.0f} MB livres".replace(",", "."),
                        "Libere espaço: cada currículo ocupa ~200 KB e as planilhas grandes passam de 100 MB.", TODAS)
    if nuvem:
        return Checagem(nome, AVISO, f"{raiz} está dentro de {nuvem[0]}",
                        "Pastas sincronizadas na nuvem travam o banco de extrações durante a coleta. "
                        "Prefira uma pasta local (ex.: C:\\Extrator Lattes).", TODAS)
    return Checagem(nome, OK, f"{raiz} — {livre_mb / 1024:.1f} GB livres".replace(".", ","), "", TODAS)


def checar_sqlite() -> Checagem:
    try:
        con = sqlite3.connect(":memory:")
        con.execute("CREATE VIRTUAL TABLE t USING fts5(x, tokenize='unicode61 remove_diacritics 2')")
        con.execute("INSERT INTO t VALUES ('canabidiol')")
        n = con.execute("SELECT count(*) FROM t WHERE t MATCH 'canabidiol'").fetchone()[0]
        con.close()
        if n != 1:
            raise sqlite3.Error("busca não encontrou o texto inserido")
    except sqlite3.Error as e:
        return Checagem("Banco de dados (SQLite FTS5)", ERRO, str(e),
                        "A busca na base de currículos não vai funcionar. Atualize o programa.", (BASE,))
    return Checagem("Banco de dados (SQLite FTS5)", OK, f"SQLite {sqlite3.sqlite_version}", "", (BASE,))


def checar_cnpq(timeout: float = 8.0) -> Checagem:
    afeta = (COLETA, NOMES)
    req = urllib.request.Request(URL_CNPQ, headers={"User-Agent": "Mozilla/5.0"})
    # O servidor do CNPq só negocia cifras que o OpenSSL atual recusa no nível padrão; o Chrome
    # aceita. Baixa só o nível de cifra (o certificado continua verificado): é só um teste de alcance.
    ctx = ssl.create_default_context()
    ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return Checagem("Acesso ao CNPq", OK, f"buscatextual.cnpq.br respondeu ({r.status})", "", afeta)
    except urllib.error.HTTPError as e:
        # respondeu, mesmo que com erro: rede e DNS funcionam
        return Checagem("Acesso ao CNPq", AVISO, f"buscatextual.cnpq.br respondeu {e.code}",
                        "O site do CNPq pode estar instável agora. Tente a coleta mais tarde.", afeta)
    except Exception as e:
        motivo = getattr(e, "reason", e)
        if isinstance(motivo, ssl.SSLError) and not isinstance(motivo, ssl.SSLCertVerificationError):
            # chegou ao servidor (DNS e rota ok); só a negociação TLS do Python falhou
            return Checagem("Acesso ao CNPq", OK, "buscatextual.cnpq.br alcançável", "", afeta)
        return Checagem("Acesso ao CNPq", AVISO, f"Sem resposta de buscatextual.cnpq.br: {motivo}",
                        "Confira a internet ou o proxy/firewall. Gerar planilhas e a base funcionam offline.", afeta)


def checagens(cfg: Config, rede: bool = True) -> list[Callable[[], Checagem]]:
    lista: list[Callable[[], Checagem]] = [
        checar_arquivos_internos,
        lambda: checar_pasta_trabalho(cfg),
        checar_selenium,
        _modulos("Leitura de currículos (lxml)", TODAS, "O executável está incompleto. Atualize o programa.",
                 "lxml.html:fromstring", "lxml.etree:XPath"),
        _modulos("Planilhas Excel (xlsxwriter, openpyxl)", (PLANILHA, NOMES, COLETA),
                 "O executável está incompleto. Atualize o programa.",
                 "xlsxwriter:Workbook", "openpyxl:load_workbook"),
        _modulos("Correção de acentos (ftfy)", TODAS, "O executável está incompleto. Atualize o programa.",
                 "ftfy:fix_text"),
        checar_desempate,
        checar_sqlite,
        checar_chrome,
    ]
    if rede:
        lista.append(checar_cnpq)
    return lista


def executar(cfg: Config | None = None, rede: bool = True,
             extras: list[Callable[[], Checagem]] | None = None) -> Resultado:
    """Roda todas as checagens; nenhuma exceção escapa (vira ``ERRO`` na própria checagem)."""
    cfg = cfg or Config.carregar()
    res = Resultado()
    for fn in checagens(cfg, rede) + list(extras or []):
        t0 = time.perf_counter()
        try:
            c = fn()
        except Exception as e:
            nome = getattr(fn, "__name__", "checagem").replace("checar_", "").replace("_", " ")
            c = Checagem(nome, ERRO, f"{type(e).__name__}: {e}", "Avise quem mantém o programa.", TODAS)
        c.segundos = round(time.perf_counter() - t0, 3)
        res.checagens.append(c)
    return res


def texto(res: Resultado) -> str:
    marca = {OK: "[ ok ]", AVISO: "[aviso]", ERRO: "[ERRO]"}
    linhas = []
    for c in res.checagens:
        linhas.append(f"{marca[c.status]} {c.nome}" + (f" — {c.detalhe}" if c.detalhe else ""))
        if c.dica and not c.ok:
            linhas.append(f"         {c.dica}")
    linhas.append(res.resumo())
    return "\n".join(linhas)

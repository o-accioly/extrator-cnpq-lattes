"""Configurações persistentes do extrator (JSON na pasta de dados do usuário)."""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

PALAVRAS_CHAVE_PADRAO = [
    "cannabis", "cannabidiol", "canabidiol", "canhamo", "canabinologia",
    "tetrahidrocanabinol", "canabinoide", "cannabinoid", "cbd", "thc",
]


def pasta_dados_usuario() -> Path:
    """Pasta de configuração por usuário (Windows: %APPDATA%, Linux: ~/.config)."""
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "ExtratorLattes"


def pasta_trabalho_padrao() -> Path:
    docs = Path.home() / "Documents"
    if not docs.exists():
        docs = Path.home() / "Documentos" if (Path.home() / "Documentos").exists() else Path.home()
    return docs / "Extrator Lattes"


@dataclass
class Config:
    # Onde ficam currículos, planilhas, banco de extrações e o perfil do Chrome
    pasta_trabalho: str = field(default_factory=lambda: str(pasta_trabalho_padrao()))

    # Coleta (navegador)
    atraso_entre_curriculos: float = 5.0     # segundos, com variação aleatória de ±30%
    atraso_entre_buscas: float = 2.0         # entre buscas de nomes
    timeout_pagina: int = 30
    resultados_por_pagina: int = 100         # 10, 20, 50 ou 100 (opções do CNPq)
    espera_bloqueio: int = 300               # se a listagem some (bloqueio), espera e recarrega
    alerta_sonoro: bool = True
    chrome_perfil_persistente: bool = True   # mantém cookies entre execuções

    # Processamento
    processos: int = 0                       # 0 = automático (núcleos da CPU)
    palavras_chave: list[str] = field(default_factory=lambda: list(PALAVRAS_CHAVE_PADRAO))
    siglas_palavra_inteira: list[str] = field(default_factory=lambda: ["cbd", "thc"])
    gerar_tsv: bool = True
    abrir_planilha_ao_terminar: bool = True

    # Busca por nomes
    nota_minima: float = 0.60                # confiança mínima para aceitar um perfil
    margem_desempate: float = 0.12           # vantagem mínima do 1º sobre o 2º
    max_candidatos_cv: int = 5               # quantos CVs completos baixar para desempatar
    similaridade_nome: int = 88              # 0-100, corte por semelhança do nome

    # Interface
    mostrar_intro: bool = True

    @property
    def raiz(self) -> Path:
        return Path(self.pasta_trabalho)

    @property
    def pasta_htmls(self) -> Path:
        return self.raiz / "htmls"

    @property
    def pasta_planilhas(self) -> Path:
        return self.raiz / "planilhas"

    @property
    def banco(self) -> Path:
        return self.raiz / "extracoes.sqlite3"

    @property
    def perfil_chrome(self) -> Path:
        return self.raiz / ".chrome-perfil"

    def num_processos(self) -> int:
        return self.processos if self.processos > 0 else max(1, (os.cpu_count() or 2) - 1)

    def garantir_pastas(self) -> None:
        for p in (self.raiz, self.pasta_htmls, self.pasta_planilhas):
            p.mkdir(parents=True, exist_ok=True)

    # --- persistência ---
    @staticmethod
    def arquivo() -> Path:
        return pasta_dados_usuario() / "config.json"

    @classmethod
    def carregar(cls) -> "Config":
        cfg = cls()
        try:
            dados = json.loads(cls.arquivo().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cfg
        validos = {f.name for f in fields(cls)}
        for k, v in dados.items():
            if k in validos:
                setattr(cfg, k, v)
        return cfg

    def salvar(self) -> None:
        arq = self.arquivo()
        arq.parent.mkdir(parents=True, exist_ok=True)
        tmp = arq.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(arq)

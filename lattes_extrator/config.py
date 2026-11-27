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


def pasta_local_usuario() -> Path:
    """Dados locais que não devem ir para a nuvem (Windows: %LOCALAPPDATA%, fora do roaming)."""
    if sys.platform.startswith("win"):
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "ExtratorLattes"
    return pasta_dados_usuario()


def pasta_trabalho_padrao() -> Path:
    docs = Path.home() / "Documents"
    if not docs.exists():
        docs = Path.home() / "Documentos" if (Path.home() / "Documentos").exists() else Path.home()
    return docs / "Extrator Lattes"


# Faixas aceitas ao carregar o config.json (valor fora vira o limite mais próximo)
LIMITES: dict[str, tuple[float, float]] = {
    "atraso_entre_curriculos": (1, 120), "atraso_entre_buscas": (0.5, 60), "timeout_pagina": (10, 300),
    "espera_bloqueio": (30, 3600), "processos": (0, 64), "nota_minima": (0.1, 1.0),
    "margem_desempate": (0.0, 0.8), "max_candidatos_cv": (0, 20), "similaridade_nome": (50, 100),
}
POR_PAGINA = (10, 20, 50, 100)


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
        """Perfil do Chrome usado na coleta. Fica nos dados locais do usuário: dentro da pasta de
        trabalho ele ia junto para o OneDrive/Dropbox (centenas de MB e arquivos travados).
        Quem já tinha o perfil na pasta de trabalho continua usando o mesmo."""
        antigo = self.raiz / ".chrome-perfil"
        return antigo if antigo.is_dir() else pasta_local_usuario() / "chrome-perfil"

    def num_processos(self) -> int:
        return self.processos if self.processos > 0 else max(1, (os.cpu_count() or 2) - 1)

    def garantir_pastas(self) -> None:
        for p in (self.raiz, self.pasta_htmls, self.pasta_planilhas):
            p.mkdir(parents=True, exist_ok=True)

    def garantir_pastas_ou_padrao(self) -> str:
        """Como ``garantir_pastas``, mas se a pasta configurada não der para usar (pen drive
        removido, rede fora, sem permissão) volta para a padrão em vez de impedir o programa
        de abrir. Devolve o aviso para mostrar à pessoa ("" se deu tudo certo)."""
        try:
            self.garantir_pastas()
            return ""
        except OSError as e:
            anterior = self.pasta_trabalho
            self.pasta_trabalho = str(pasta_trabalho_padrao())
            self.garantir_pastas()
            return (f"A pasta de trabalho {anterior} não está acessível ({e.strerror or e}). "
                    f"Usando {self.pasta_trabalho} nesta sessão; ajuste em Configurações.")

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
        if not isinstance(dados, dict):
            return cfg
        padrao = {f.name: getattr(cfg, f.name) for f in fields(cls)}
        for k, v in dados.items():
            if k in padrao:
                setattr(cfg, k, _validar(k, v, padrao[k]))
        return cfg

    def salvar(self) -> None:
        arq = self.arquivo()
        arq.parent.mkdir(parents=True, exist_ok=True)
        tmp = arq.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(arq)


def _validar(chave: str, valor, padrao):
    """Converte para o tipo do padrão e prende na faixa aceita; valor inválido vira o padrão
    (um config.json editado à mão ou de versão antiga não pode derrubar o programa)."""
    try:
        if isinstance(padrao, bool):
            if not isinstance(valor, bool):
                return padrao
        elif isinstance(padrao, (int, float)):
            if isinstance(valor, bool) or not isinstance(valor, (int, float, str)):
                return padrao
            valor = type(padrao)(float(valor))
            if chave in LIMITES:
                lo, hi = LIMITES[chave]
                valor = type(padrao)(min(max(valor, lo), hi))
            if chave == "resultados_por_pagina" and valor not in POR_PAGINA:
                return padrao
        elif isinstance(padrao, list):
            if not isinstance(valor, list):
                return padrao
            valor = [str(x).strip() for x in valor if str(x).strip()]
        elif isinstance(padrao, str):
            valor = str(valor).strip() or padrao
    except (TypeError, ValueError):
        return padrao
    return valor

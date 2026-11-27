"""Desempate entre perfis homônimos.

Cada coluna preenchida na planilha de nomes (além do Nome) vira um critério. O valor
é comparado com o pedaço do currículo onde aquele dado costuma estar (formação,
instituição, área, endereço...). A comparação é tolerante: ignora acento e caixa,
aceita siglas e pequenas diferenças de grafia, e uma célula pode trazer vários
valores separados por ";" (qualquer um que bata conta).

Há dois níveis de dados por candidato:
* leve: linha da listagem + janela de detalhes (rápido, sem captcha);
* completo: o currículo inteiro, baixado só quando o leve não basta.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .texto import normalizar

try:
    from rapidfuzz import fuzz
except ImportError:  # fallback sem dependência compilada
    import difflib

    class fuzz:  # type: ignore[no-redef]
        @staticmethod
        def partial_ratio(a: str, b: str) -> float:
            if not a or not b:
                return 0.0
            if len(a) > len(b):
                a, b = b, a
            m = difflib.SequenceMatcher(None, a, b, autojunk=False)
            melhor = 0.0
            for bloco in m.get_matching_blocks():
                ini = max(0, bloco.b - bloco.a)
                melhor = max(melhor, difflib.SequenceMatcher(None, a, b[ini:ini + len(a)]).ratio())
            return 100 * melhor

        @staticmethod
        def token_sort_ratio(a: str, b: str) -> float:
            return 100 * difflib.SequenceMatcher(None, " ".join(sorted(a.split())), " ".join(sorted(b.split()))).ratio()

UFS = {
    "ac": "acre", "al": "alagoas", "ap": "amapa", "am": "amazonas", "ba": "bahia", "ce": "ceara",
    "df": "distrito federal", "es": "espirito santo", "go": "goias", "ma": "maranhao", "mt": "mato grosso",
    "ms": "mato grosso do sul", "mg": "minas gerais", "pa": "para", "pb": "paraiba", "pr": "parana",
    "pe": "pernambuco", "pi": "piaui", "rj": "rio de janeiro", "rn": "rio grande do norte",
    "rs": "rio grande do sul", "ro": "rondonia", "rr": "roraima", "sc": "santa catarina", "sp": "sao paulo",
    "se": "sergipe", "to": "tocantins",
}


@dataclass(frozen=True)
class Criterio:
    chave: str
    cabecalho: str
    descricao: str
    exemplo: str
    aliases: tuple[str, ...]
    campos_completos: tuple[str, ...]   # colunas do currículo completo onde procurar
    peso: float = 1.0
    tipo: str = "texto"                 # texto | ano | uf | id | orcid


CRITERIOS: list[Criterio] = [
    Criterio("id_lattes", "ID Lattes", "Se já souber o ID de 16 dígitos ou o link, o perfil é confirmado direto.",
             "1234567890123456", ("id lattes", "lattes", "link lattes", "id", "link"), ("ID Lattes",), 6, "id"),
    Criterio("orcid", "ORCID", "Identificador ORCID; confirma o perfil quando bate.",
             "0000-0003-0723-2587", ("orcid", "orcid id"), ("ORCID",), 6, "orcid"),
    Criterio("titulacao", "Formação (nível)", "Maior titulação ou nível de formação: Doutorado, Mestrado...",
             "Doutorado", ("formacao", "nivel", "nivel de formacao", "titulacao", "maior titulacao", "formacao nivel"),
             ("Maior titulação", "Formação acadêmica/titulação", "Pós-doutorado")),
    Criterio("curso", "Curso / área de formação", "Nome do curso, ex.: Farmácia, Medicina, Ciências Farmacêuticas.",
             "Farmácia", ("curso", "area de formacao", "graduacao", "especialidade", "especializacao"),
             ("Formação acadêmica/titulação", "Formação Complementar", "Áreas de atuação")),
    Criterio("inst_formacao", "Instituição de formação", "Onde se formou (nome ou sigla). Vários separados por ;",
             "UFPE", ("instituicao de formacao", "universidade", "faculdade", "onde se formou", "instituicao formacao"),
             ("Instituição da maior titulação", "Formação acadêmica/titulação")),
    Criterio("ano_formacao", "Ano de formação", "Ano de conclusão de algum curso (aceita ±1 ano).",
             "1992", ("ano", "ano de formacao", "ano de conclusao", "ano titulacao"),
             ("Ano da maior titulação", "Formação acadêmica/titulação"), 0.8, "ano"),
    Criterio("uf_formacao", "UF de formação", "Estado onde se formou (sigla ou nome).",
             "PE", ("uf de formacao", "estado de formacao", "uf formacao"),
             ("Formação acadêmica/titulação", "Instituição da maior titulação"), 0.8, "uf"),
    Criterio("area", "Área de atuação", "Grande área, área ou especialidade de atuação.",
             "Tecnologia Farmacêutica", ("area", "area de atuacao", "atuacao", "especialidade de atuacao"),
             ("Áreas de atuação", "Linhas de pesquisa", "Resumo")),
    Criterio("inst_atual", "Instituição onde trabalha", "Instituição de vínculo atual ou anterior (nome ou sigla).",
             "Universidade Federal de Pernambuco", ("instituicao", "instituicao atual", "empresa", "trabalha em",
                                                    "vinculo", "organizacao", "instituicao de atuacao"),
             ("Instituição atual", "Atuação profissional", "Endereço profissional")),
    Criterio("uf", "UF / cidade de atuação", "Estado ou cidade onde atua (endereço profissional).",
             "PE", ("uf", "estado", "cidade", "municipio", "uf de atuacao", "local"),
             ("Endereço profissional", "Instituição atual"), 0.8, "uf"),
    Criterio("palavras", "Palavras-chave", "Termos que devem aparecer no currículo (tema de pesquisa etc.).",
             "cannabis; canabidiol", ("palavras chave", "palavras", "tema", "assunto", "palavra chave"),
             ("Resumo", "Linhas de pesquisa", "Projetos de pesquisa", "Artigos completos publicados em periódicos",
              "Áreas de atuação"), 0.7),
    Criterio("citacoes", "Nome em citações", "Forma do nome usada em artigos, ex.: VASCONCELOS, A. B. E.",
             "VASCONCELOS, A. B. E.", ("nome em citacoes", "citacao", "nome citacao", "citacoes"),
             ("Nome em citações bibliográficas",), 1.2),
]
POR_CHAVE = {c.chave: c for c in CRITERIOS}


def identificar_coluna(cabecalho: str, colunas_cv: list[str] | None = None) -> tuple[str, str] | None:
    """Mapeia um cabeçalho da planilha para ('criterio', chave) ou ('coluna', nome da coluna do CV)."""
    n = normalizar(cabecalho)
    if not n or n in ("nome", "nome completo", "pesquisador", "nome do pesquisador"):
        return None
    for c in CRITERIOS:
        if n == normalizar(c.cabecalho) or n in c.aliases:
            return ("criterio", c.chave)
    for col in colunas_cv or []:
        if n == normalizar(col):
            return ("coluna", col)
    return ("coluna", cabecalho)


def separar_valores(valor: str) -> list[str]:
    return [v.strip() for v in re.split(r"[;|\n]+", str(valor)) if v.strip()]


def _sim_texto(valor: str, texto: str) -> float:
    v, t = normalizar(valor), normalizar(texto)
    if not v or not t:
        return 0.0
    if re.search(rf"\b{re.escape(v)}\b", t):
        return 1.0
    if len(v) <= 3:          # siglas curtas: só igualdade de palavra
        return 0.0
    s = fuzz.partial_ratio(v, t) / 100
    return s if s >= 0.75 else s * 0.5


def _sim_ano(valor: str, texto: str) -> float:
    m = re.search(r"(19|20)\d{2}", str(valor))
    if not m:
        return 0.0
    ano = int(m.group(0))
    anos = {int(a) for a in re.findall(r"\b(?:19|20)\d{2}\b", texto)}
    if ano in anos:
        return 1.0
    return 0.5 if (ano - 1 in anos or ano + 1 in anos) else 0.0


def _sim_uf(valor: str, texto: str) -> float:
    v = normalizar(valor)
    t = normalizar(texto)
    nome = UFS.get(v, v)
    sigla = next((s for s, n in UFS.items() if n == v), v if v in UFS else "")
    if nome and re.search(rf"\b{re.escape(nome)}\b", t):
        return 1.0
    if sigla and re.search(rf"\b{sigla}\b", t):
        return 0.9
    return _sim_texto(valor, texto) if len(v) > 3 else 0.0


def _sim_id(valor: str, texto: str) -> float:
    a = re.sub(r"\D", "", str(valor))
    return 1.0 if len(a) >= 10 and a in re.sub(r"\D", " ", texto).split() else 0.0


def _sim_orcid(valor: str, texto: str) -> float:
    m = re.search(r"\d{4}-\d{4}-\d{4}-\d{3}[\dXx]", str(valor))
    return 1.0 if m and m.group(0).upper() in texto.upper() else 0.0


SIMILARIDADES = {"texto": _sim_texto, "ano": _sim_ano, "uf": _sim_uf, "id": _sim_id, "orcid": _sim_orcid}


def similaridade_nome(buscado: str, encontrado: str) -> int:
    a, b = normalizar(buscado), normalizar(encontrado)
    if not a or not b:
        return 0
    base = fuzz.token_sort_ratio(a, b)
    ligacao = {"de", "da", "do", "dos", "das", "e"}
    ta, tb = set(a.split()) - ligacao, set(b.split()) - ligacao
    if ta and ta <= tb and len(ta) >= 2:
        # Todos os nomes buscados estão no encontrado (ex.: faltou o nome do meio).
        # Cada nome a mais no encontrado reduz a nota: 1 a mais = 90, 2 = 85, 3 = 80.
        extras = len(tb - ta)
        base = max(base, 100 if extras == 0 else 95 - 5 * extras)
    return int(round(max(0, base)))


@dataclass
class Avaliacao:
    nota: float                               # 0..1
    detalhes: dict[str, float] = field(default_factory=dict)  # cabeçalho -> similaridade
    completo: bool = False

    def explicar(self) -> str:
        if not self.detalhes:
            return "sem critérios"
        return ", ".join(f"{k} {v:.0%}" for k, v in sorted(self.detalhes.items(), key=lambda x: -x[1]))


def avaliar(criterios: dict[str, str], linha_cv: dict | None, texto_leve: str, id16: str = "") -> Avaliacao:
    """``criterios``: cabeçalho da planilha -> valor. ``linha_cv``: currículo completo
    (``Curriculo.como_linha()``) ou None para avaliar só com os dados leves."""
    if not criterios:
        return Avaliacao(0.0, {}, linha_cv is not None)
    soma = pesos = 0.0
    detalhes: dict[str, float] = {}
    for cabecalho, valor in criterios.items():
        alvo = identificar_coluna(cabecalho)
        if alvo is None:
            continue
        tipo_alvo, chave = alvo
        crit = POR_CHAVE.get(chave) if tipo_alvo == "criterio" else None
        tipo = crit.tipo if crit else "texto"
        peso = crit.peso if crit else 1.0
        if linha_cv is not None:
            campos = crit.campos_completos if crit else (chave,)
            texto = " \n ".join(str(linha_cv.get(c, "")) for c in campos if linha_cv.get(c))
            if crit and crit.chave == "palavras":
                texto += " " + " ".join(str(v) for v in linha_cv.values() if isinstance(v, str))
        else:
            texto = texto_leve + (f" {id16}" if id16 else "")
        if not texto.strip():
            continue  # dado ausente: não conta a favor nem contra
        fn = SIMILARIDADES[tipo]
        s = max(fn(v, texto) for v in separar_valores(valor))
        if linha_cv is None and s == 0 and tipo in ("texto", "uf", "ano"):
            continue  # nos dados leves a ausência não prova nada
        detalhes[cabecalho] = s
        soma += s * peso
        pesos += peso
    nota = soma / pesos if pesos else 0.0
    return Avaliacao(nota, detalhes, linha_cv is not None)


def decidir(avaliacoes: list[tuple[object, Avaliacao]], nota_minima: float, margem: float) -> tuple[object | None, str]:
    """Escolhe o vencedor. Devolve (candidato ou None, motivo)."""
    if not avaliacoes:
        return None, "nenhum candidato"
    ordem = sorted(avaliacoes, key=lambda x: -x[1].nota)
    melhor, av = ordem[0]
    if any(v >= 1.0 and k.lower().startswith(("id", "orcid")) for k, v in av.detalhes.items()):
        return melhor, "identificador confere"
    segundo = ordem[1][1].nota if len(ordem) > 1 else 0.0
    if av.nota >= nota_minima and (av.nota - segundo) >= margem:
        return melhor, f"melhor nota {av.nota:.0%} (2º: {segundo:.0%})"
    return None, f"empate ou nota baixa: 1º {av.nota:.0%}, 2º {segundo:.0%}"

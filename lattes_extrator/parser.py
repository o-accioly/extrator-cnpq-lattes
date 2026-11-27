"""Leitura do HTML de um currículo Lattes e conversão em um registro plano (uma linha).

O HTML do Lattes é organizado em seções ``div.title-wrapper`` (com um ``h1``). Dentro
de cada seção os dados vêm numa sequência "plana" de blocos:

* ``div.inst_back``    -> cabeçalho de grupo (instituição, "Produção bibliográfica"...)
* ``div.cita-artigos`` -> cabeçalho de subseção ("Artigos completos publicados em ...")
* ``div.layout-cell-11`` / ``div.artigo-completo`` -> um item de produção
* ``div.layout-cell-3`` + ``div.layout-cell-9``     -> par rótulo/valor (datas, campos)
* ``div.science_cont`` -> métricas de citação (Web of Science, Scopus, SciELO)

O parser percorre cada seção uma única vez, em ordem, mantendo grupo e subseção
correntes. Cada combinação (seção, grupo, subseção) vira uma coluna. Usa lxml puro,
cerca de 10x mais rápido que BeautifulSoup.
"""
from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass, field

import lxml.html

from .texto import decodificar_html, limpar, normalizar, sem_acentos

# ---------------------------------------------------------------------------
# Colunas fixas (sempre presentes, nesta ordem)
# ---------------------------------------------------------------------------
COLUNAS_FIXAS = [
    "ID Lattes", "Código CNPq", "Link Lattes", "Nome", "Nome em citações bibliográficas",
    "ORCID", "País de nacionalidade", "Bolsa de produtividade", "Última atualização",
    "Maior titulação", "Ano da maior titulação", "Instituição da maior titulação",
    "Instituição atual", "Endereço profissional", "Áreas de atuação", "Resumo",
    "Outras informações relevantes", "Atuação profissional",
    "Produção bibliográfica (total)",
    "Qtd. artigos em periódicos", "Qtd. livros", "Qtd. capítulos de livros",
    "Qtd. trabalhos completos em anais", "Qtd. resumos em anais",
    "Qtd. orientações concluídas", "Qtd. orientações em andamento",
    "Qtd. projetos de pesquisa", "Qtd. patentes e registros",
    "Web of Science: trabalhos", "Web of Science: citações", "Web of Science: fator H",
    "Scopus: trabalhos", "Scopus: citações", "Scopus: fator H",
    "SciELO: trabalhos", "SciELO: citações",
]

# Descrição de cada coluna fixa (vai para a aba "Dicionário" e para o template)
DESCRICOES = {
    "ID Lattes": "Identificador de 16 dígitos do currículo (lattes.cnpq.br/ID)",
    "Código CNPq": "Código interno de 10 caracteres usado pela busca (ex.: K0000000A1)",
    "Link Lattes": "Endereço público do currículo",
    "Nome": "Nome completo do pesquisador",
    "Nome em citações bibliográficas": "Formas do nome usadas em publicações",
    "ORCID": "Identificador ORCID",
    "País de nacionalidade": "País de nacionalidade",
    "Bolsa de produtividade": "Categoria/nível da bolsa de produtividade do CNPq, se houver",
    "Última atualização": "Data da última atualização do currículo",
    "Maior titulação": "Maior nível de formação concluído (Doutorado, Mestrado...)",
    "Ano da maior titulação": "Ano de conclusão da maior titulação",
    "Instituição da maior titulação": "Instituição onde obteve a maior titulação",
    "Instituição atual": "Instituição do vínculo profissional atual",
    "Endereço profissional": "Endereço profissional declarado",
    "Áreas de atuação": "Grande área / área / subárea / especialidade",
    "Resumo": "Texto de apresentação do currículo",
    "Outras informações relevantes": "Campo livre do currículo",
    "Atuação profissional": "Vínculos agrupados por instituição",
    "Produção bibliográfica (total)": "Artigos + livros + capítulos + trabalhos completos em anais",
}

PRODUCAO_TOTAL = {
    "Artigos completos publicados em periódicos",
    "Livros publicados/organizados ou edições",
    "Capítulos de livros publicados",
    "Trabalhos completos publicados em anais de congressos",
}

CONTAGENS = {
    "Qtd. artigos em periódicos": ["Artigos completos publicados em periódicos"],
    "Qtd. livros": ["Livros publicados/organizados ou edições"],
    "Qtd. capítulos de livros": ["Capítulos de livros publicados"],
    "Qtd. trabalhos completos em anais": ["Trabalhos completos publicados em anais de congressos"],
    "Qtd. resumos em anais": ["Resumos publicados em anais de congressos",
                              "Resumos expandidos publicados em anais de congressos"],
}

NIVEIS_FORMACAO = [  # do maior para o menor
    ("livre-docencia", "Livre-docência"),
    ("pos-doutorado", "Pós-doutorado"),
    ("doutorado", "Doutorado"),
    ("mestrado profissional", "Mestrado profissional"),
    ("mestrado", "Mestrado"),
    ("especializacao", "Especialização"),
    ("aperfeicoamento", "Aperfeiçoamento"),
    ("residencia", "Residência médica"),
    ("graduacao", "Graduação"),
    ("ensino medio", "Ensino médio"),
    ("ensino fundamental", "Ensino fundamental"),
]

# Seções que viram campos fixos e não geram coluna própria
SECOES_FIXAS = {"Identificacao", "Endereco"}

RE_ID16 = re.compile(r"\b(\d{16})\b")
RE_KID = re.compile(r"[?&]id=([A-Z0-9]{10})\b")
RE_ORCID = re.compile(r"\b(\d{4}-\d{4}-\d{4}-\d{3}[\dX])\b")
RE_ANO = re.compile(r"(?:19|20)\d{2}")
RE_NUM = re.compile(r"(\d[\d.]*)")


def _classes(el) -> set[str]:
    c = el.get("class")
    return set(c.split()) if c else set()


def _txt(el) -> str:
    """Texto do elemento com espaço entre nós (lxml.text_content gruda '<br>')."""
    return limpar(" ".join(t for t in el.itertext()))


def _item_artigo(el) -> str:
    """Texto de um artigo sem os spans ocultos de ordenação e o bloco de citações."""
    celula = el.find(".//div[@class]")
    for c in el.iter("div"):
        if "layout-cell-11" in _classes(c):
            celula = c
            break
    if celula is None:
        return ""
    for oculto in celula.xpath('.//span[contains(@class,"informacao-artigo") or contains(@class,"citado")]'):
        oculto.drop_tree()
    return _txt(celula)


@dataclass
class Secao:
    ancora: str
    titulo: str
    # (grupo, subseção) -> itens, na ordem do documento
    blocos: "OrderedDict[tuple[str, str], list[str]]" = field(default_factory=OrderedDict)
    pares: list[tuple[str, str]] = field(default_factory=list)     # (rótulo, valor)
    metricas: dict[str, str] = field(default_factory=dict)
    texto: str = ""

    def adicionar(self, grupo: str, sub: str, item: str) -> None:
        if not item:
            return
        lista = self.blocos.setdefault((grupo, sub), [])
        if item not in lista:
            lista.append(item)


def _ler_secao(wrapper, ancora: str, titulo: str) -> Secao:
    sec = Secao(ancora, titulo)
    estado = {"grupo": "", "sub": "", "rotulo": None}

    def visitar(el):
        for filho in el:
            if not isinstance(filho.tag, str):  # comentários, instruções
                continue
            if filho.tag in ("script", "style", "select", "h1", "label", "noscript"):
                continue
            cls = _classes(filho)
            if "inst_back" in cls:
                estado.update(grupo=_txt(filho).rstrip(". "), sub="", rotulo=None)
            elif "cita-artigos" in cls:
                estado.update(sub=_txt(filho), rotulo=None)
            elif "artigo-completo" in cls:
                sec.adicionar(estado["grupo"], estado["sub"], _item_artigo(filho))
            elif "layout-cell-11" in cls:
                sec.adicionar(estado["grupo"], estado["sub"], _txt(filho))
            elif "layout-cell-3" in cls:
                estado["rotulo"] = _txt(filho)
            elif "layout-cell-9" in cls:
                valor, rotulo = _txt(filho), estado["rotulo"] or ""
                estado["rotulo"] = None
                if not valor or rotulo == "Vínculo institucional":
                    continue
                sec.pares.append((rotulo, valor))
                numerado = bool(re.fullmatch(r"\d+\.?", rotulo))
                item = valor if (not rotulo or numerado) else f"{rotulo}: {valor}"
                sec.adicionar(estado["grupo"], estado["sub"], item)
            elif "science_cont" in cls:
                _ler_metricas(filho, sec.metricas)
            else:
                visitar(filho)

    visitar(wrapper)
    if not sec.blocos and not sec.pares and not sec.metricas:
        partes = [t for t in wrapper.itertext()]
        texto = limpar(" ".join(partes))
        if texto.startswith(titulo):
            texto = texto[len(titulo):].strip()
        sec.texto = texto
    return sec


def _ler_metricas(el, destino: dict[str, str]) -> None:
    base = ""
    for d in el.iter("div"):
        cls = _classes(d)
        if "web_s" in cls:
            base = _txt(d)
    if not base:
        return
    base = {"web of science": "Web of Science", "scopus": "Scopus", "scielo": "SciELO"}.get(base.lower(), base)
    texto = _txt(el)
    for rotulo, chave in (("Total de trabalhos", "trabalhos"), ("Total de citações", "citações"), ("Fator H", "fator H")):
        m = re.search(re.escape(rotulo) + r":\s*(\d+)", texto)
        if m:
            destino[f"{base}: {chave}"] = m.group(1)


@dataclass
class Curriculo:
    campos: "OrderedDict[str, object]"
    secoes: "OrderedDict[str, str]"       # colunas dinâmicas (texto)
    contagens: dict[str, int]             # itens por coluna dinâmica

    @property
    def id_lattes(self) -> str:
        return str(self.campos.get("ID Lattes") or "")

    @property
    def nome(self) -> str:
        return str(self.campos.get("Nome") or "")

    def como_linha(self) -> "OrderedDict[str, object]":
        linha = OrderedDict(self.campos)
        linha.update(self.secoes)
        return linha


def _maior_titulacao(pares: list[tuple[str, str]]) -> tuple[str, str, str]:
    """(nível, ano, instituição) da maior formação concluída."""
    melhor = None
    for rotulo, valor in pares:
        chave = normalizar(valor.split(". ")[0])          # "doutorado", "mestrado em ..."
        em_andamento = "andamento" in normalizar(valor) or "atual" in normalizar(rotulo)
        for rank, (padrao, nome) in enumerate(NIVEIS_FORMACAO):
            if normalizar(padrao) in chave:
                if em_andamento:
                    break
                if melhor is None or rank < melhor[0]:
                    anos = RE_ANO.findall(rotulo) or RE_ANO.findall(valor)
                    partes = [p.strip() for p in valor.split(". ") if p.strip()]
                    inst = partes[1] if len(partes) > 1 else ""
                    melhor = (rank, nome, anos[-1] if anos else "", inst.rstrip("."))
                break
    if not melhor:
        return "", "", ""
    return melhor[1], melhor[2], melhor[3]


VINCULOS_PRINCIPAIS = ("servidor", "celetista", "professor", "docente", "pesquisador", "empregado", "efetivo")


def _atuacao(sec: Secao, endereco: str) -> tuple[str, str]:
    """Texto agrupado por instituição e a instituição do vínculo atual.

    Vários vínculos podem estar "Atual" (colaborador, visitante...). A escolha segue:
    1) a que aparece no endereço profissional; 2) a de vínculo empregatício
    (servidor, celetista, professor...); 3) a primeira atual; 4) a do endereço."""
    por_inst: "OrderedDict[str, list[str]]" = OrderedDict()
    for (grupo, _sub), itens in sec.blocos.items():
        inst = grupo or "Sem instituição"
        lista = por_inst.setdefault(inst, [])
        lista.extend(i for i in itens if i not in lista)
    texto = " | ".join(f"{inst}: [{'; '.join(v)}]" for inst, v in por_inst.items())

    atuais = [inst for inst, itens in por_inst.items()
              if any(re.search(r"\bAtual\b", i.split(":")[0]) for i in itens)]
    end_n = normalizar(endereco)
    for inst in atuais:
        nome_inst = normalizar(inst.split(",")[0])
        if nome_inst and end_n.startswith(nome_inst):
            return texto, inst
    for inst in atuais:
        vinc = " ".join(i for i in por_inst[inst] if re.search(r"\bAtual\b", i.split(":")[0])).lower()
        if any(v in normalizar(vinc) for v in VINCULOS_PRINCIPAIS):
            return texto, inst
    if atuais:
        return texto, atuais[0]
    return texto, endereco.split(",")[0].strip() if endereco else ""


def _nomes_colunas(secoes: list[Secao]) -> "OrderedDict[tuple[str, str, str], str]":
    """Dá nome a cada bloco (seção, grupo, subseção). Quando o mesmo nome aparece em
    lugares diferentes (ex.: "Dissertação de mestrado" em orientações em andamento e
    concluídas), prefixa com o grupo para não misturar."""
    chaves: list[tuple[str, str, str]] = []
    for s in secoes:
        if s.ancora in SECOES_FIXAS or s.ancora == "AtuacaoProfissional":
            continue
        for (grupo, sub) in s.blocos:
            chaves.append((s.titulo, grupo, sub))
        if s.texto and not s.blocos:
            chaves.append((s.titulo, "", ""))

    base = {k: (k[2] or k[1] or k[0]) for k in chaves}
    origem: dict[str, set] = {}
    for k, nome in base.items():
        origem.setdefault(nome, set()).add(k)
    nomes: "OrderedDict[tuple[str, str, str], str]" = OrderedDict()
    for k in chaves:
        nome = base[k]
        if len(origem[nome]) > 1:
            prefixo = k[1] if (k[1] and k[2]) else k[0]
            # Na própria seção de mesmo nome ("Projetos de pesquisa" dentro de
            # "Projetos de pesquisa") fica o nome simples; as outras ganham prefixo.
            if normalizar(prefixo) != normalizar(nome):
                nome = f"{prefixo} > {nome}"
        nomes[k] = nome
    return nomes


def parse_curriculo(html: str | bytes, id_arquivo: str = "") -> Curriculo:
    if isinstance(html, bytes):
        html = decodificar_html(html)
    doc = lxml.html.fromstring(html)

    campos: "OrderedDict[str, object]" = OrderedDict((c, "") for c in COLUNAS_FIXAS)

    # --- cabeçalho ---
    nomes_h2 = doc.xpath('//div[@class="infpessoa"]/h2[contains(@class,"nome")]')
    if nomes_h2:
        campos["Nome"] = _txt(nomes_h2[0])
        if len(nomes_h2) > 1:
            campos["Bolsa de produtividade"] = _txt(nomes_h2[1])
    for li in doc.xpath('//ul[@class="informacoes-autor"]/li'):
        t = _txt(li)
        if t.startswith("ID Lattes"):
            m = RE_ID16.search(t)
            if m:
                campos["ID Lattes"] = m.group(1)
        elif "atualização do currículo" in t:
            campos["Última atualização"] = t.rsplit(" em ", 1)[-1].strip()
        elif not campos["ID Lattes"] and "acessar este CV" in t:
            m = RE_ID16.search(t)
            if m:
                campos["ID Lattes"] = m.group(1)
    if not campos["ID Lattes"]:
        m = RE_ID16.fullmatch(id_arquivo or "")
        campos["ID Lattes"] = m.group(1) if m else id_arquivo
    foto = doc.xpath('//img[contains(@class,"foto")]/@src')
    if foto:
        m = RE_KID.search(foto[0])
        if m:
            campos["Código CNPq"] = m.group(1)
    if campos["ID Lattes"] and RE_ID16.fullmatch(str(campos["ID Lattes"])):
        campos["Link Lattes"] = f"http://lattes.cnpq.br/{campos['ID Lattes']}"
    resumo = doc.xpath('//p[contains(@class,"resumo")]')
    if resumo:
        campos["Resumo"] = _txt(resumo[0])
    outras = doc.xpath('//pre[contains(@class,"outras-informacoes")]')
    if outras:
        campos["Outras informações relevantes"] = _txt(outras[0])

    # --- seções ---
    secoes: list[Secao] = []
    for wrapper in doc.xpath('//div[contains(concat(" ", normalize-space(@class), " "), " title-wrapper ")]'):
        h1 = wrapper.find(".//h1")
        titulo = _txt(h1) if h1 is not None else ""
        if not titulo:
            continue
        ancora = (wrapper.xpath("./a[@name]/@name") or [""])[0]
        secoes.append(_ler_secao(wrapper, ancora, titulo))

    metricas: dict[str, str] = {}
    atuacao: Secao | None = None
    for s in secoes:
        metricas.update(s.metricas)
        if s.ancora == "Identificacao":
            dados = dict(s.pares)
            if not campos["Nome"]:
                campos["Nome"] = dados.get("Nome", "")
            campos["Nome em citações bibliográficas"] = dados.get("Nome em citações bibliográficas", "")
            campos["País de nacionalidade"] = dados.get("País de Nacionalidade", "")
            for rotulo, valor in s.pares:
                if rotulo.lower().startswith("orcid"):
                    m = RE_ORCID.search(valor)
                    campos["ORCID"] = f"https://orcid.org/{m.group(1)}" if m else valor
        elif s.ancora == "Endereco":
            for rotulo, valor in s.pares:
                if "Profissional" in rotulo:
                    campos["Endereço profissional"] = valor
        elif s.ancora == "FormacaoAcademicaTitulacao":
            nivel, ano, inst = _maior_titulacao(s.pares)
            campos["Maior titulação"], campos["Ano da maior titulação"], campos["Instituição da maior titulação"] = nivel, ano, inst
        elif s.ancora == "AtuacaoProfissional":
            atuacao = s
        elif s.ancora == "AreasAtuacao":
            campos["Áreas de atuação"] = " ; ".join(v for _, v in s.pares)
    if atuacao is not None:
        campos["Atuação profissional"], campos["Instituição atual"] = _atuacao(atuacao, str(campos["Endereço profissional"]))
    elif campos["Endereço profissional"]:
        campos["Instituição atual"] = str(campos["Endereço profissional"]).split(",")[0].strip()

    # --- colunas dinâmicas ---
    nomes = _nomes_colunas(secoes)
    dinamicas: "OrderedDict[str, str]" = OrderedDict()
    contagens: dict[str, int] = {}
    por_sub: dict[str, int] = {}
    orientacoes = {"concluidas": 0, "andamento": 0}
    for s in secoes:
        if s.ancora == "Endereco" or s.ancora == "Identificacao" or s.ancora == "AtuacaoProfissional":
            continue
        for (grupo, sub), itens in s.blocos.items():
            nome = nomes[(s.titulo, grupo, sub)]
            dinamicas[nome] = " ; ".join(itens)
            contagens[nome] = len(itens)
            if sub:
                por_sub[sub] = por_sub.get(sub, 0) + len(itens)
            if s.ancora == "Orientacoesatividades" or normalizar(s.titulo) == "orientacoes":
                g = normalizar(grupo)
                if "concluid" in g:
                    orientacoes["concluidas"] += len(itens)
                elif "andamento" in g:
                    orientacoes["andamento"] += len(itens)
            if normalizar(s.titulo).startswith("projetos de pesquisa"):
                contagens["__projetos"] = contagens.get("__projetos", 0) + len(itens)
            if normalizar(s.titulo).startswith("patentes"):
                contagens["__patentes"] = contagens.get("__patentes", 0) + len(itens)
        if s.texto and not s.blocos:
            dinamicas[nomes[(s.titulo, "", "")]] = s.texto

    # métricas e contagens fixas
    for k, v in metricas.items():
        if k in campos:
            campos[k] = int(v)
    for col, subs in CONTAGENS.items():
        campos[col] = sum(por_sub.get(s, 0) for s in subs)
    campos["Produção bibliográfica (total)"] = sum(por_sub.get(s, 0) for s in PRODUCAO_TOTAL)
    campos["Qtd. orientações concluídas"] = orientacoes["concluidas"]
    campos["Qtd. orientações em andamento"] = orientacoes["andamento"]
    campos["Qtd. projetos de pesquisa"] = contagens.pop("__projetos", 0)
    campos["Qtd. patentes e registros"] = contagens.pop("__patentes", 0)

    # Texto visível para palavras-chave (sem script/style/head)
    visivel = doc.xpath("//body//text()[not(ancestor::script) and not(ancestor::style) and not(ancestor::noscript)]")
    cv = Curriculo(campos, dinamicas, contagens)
    cv._texto_visivel = " ".join(visivel)  # type: ignore[attr-defined]
    return cv


# ---------------------------------------------------------------------------
# Palavras-chave
# ---------------------------------------------------------------------------
def compilar_palavras(palavras: list[str], siglas: list[str]) -> "OrderedDict[str, re.Pattern]":
    """Termos longos casam como trecho (pega plurais); siglas só como palavra inteira."""
    siglas_n = {normalizar(s) for s in siglas}
    saida: "OrderedDict[str, re.Pattern]" = OrderedDict()
    for p in palavras:
        n = sem_acentos(p).lower().strip()
        if not n:
            continue
        padrao = rf"\b{re.escape(n)}\b" if normalizar(p) in siglas_n else re.escape(n)
        saida[p] = re.compile(padrao)
    return saida


def aplicar_palavras_chave(cv: Curriculo, padroes: "OrderedDict[str, re.Pattern]") -> "OrderedDict[str, object]":
    texto = sem_acentos(getattr(cv, "_texto_visivel", "")).lower()
    colunas = {k: sem_acentos(str(v)).lower() for k, v in cv.como_linha().items()
               if isinstance(v, str) and v and k not in ("Nome", "ID Lattes", "Link Lattes")}
    saida: "OrderedDict[str, object]" = OrderedDict()
    for pc, padrao in padroes.items():
        saida[f"Contagem: {pc}"] = len(padrao.findall(texto))
        saida[f"Ocorrências (colunas): {pc}"] = " ; ".join(c for c, v in colunas.items() if padrao.search(v))
    return saida

"""Planilha de entrada da busca por nomes: template para download e leitura."""
from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from pathlib import Path

from .desempate import CRITERIOS, identificar_coluna
from .parser import COLUNAS_FIXAS, DESCRICOES
from .texto import normalizar

# Seções comuns de um currículo (colunas dinâmicas) para o template listar
SECOES_COMUNS = [
    "Formação acadêmica/titulação", "Pós-doutorado", "Formação Complementar", "Linhas de pesquisa",
    "Projetos de pesquisa", "Projetos de extensão", "Projetos de desenvolvimento", "Membro de corpo editorial",
    "Revisor de periódico", "Idiomas", "Prêmios e títulos", "Artigos completos publicados em periódicos",
    "Livros publicados/organizados ou edições", "Capítulos de livros publicados",
    "Trabalhos completos publicados em anais de congressos", "Resumos publicados em anais de congressos",
    "Apresentações de Trabalho", "Produtos tecnológicos", "Patentes e registros > Patente",
    "Participação em eventos, congressos, exposições e feiras",
]

NIVEIS = ["Doutorado", "Mestrado", "Mestrado profissional", "Especialização", "Graduação", "Pós-doutorado",
          "Livre-docência", "Residência médica"]
UFS = ["AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR",
       "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"]

EXEMPLOS = [
    {"Nome": "Ana Beatriz Exemplo Vasconcelos", "Formação (nível)": "Doutorado", "Instituição de formação": "Exemple",
     "Instituição onde trabalha": "UFPE", "UF / cidade de atuação": "PE", "Palavras-chave": "cannabis"},
    {"Nome": "Maria da Silva", "Formação (nível)": "Mestrado", "Curso / área de formação": "Enfermagem",
     "UF de formação": "SP"},
]


def colunas_template() -> tuple[list[str], list[str]]:
    criterios = ["Nome"] + [c.cabecalho for c in CRITERIOS]
    ja = {normalizar(c) for c in criterios}
    outros = [c for c in COLUNAS_FIXAS + SECOES_COMUNS if normalizar(c) not in ja]
    return criterios, outros


def gerar_template(caminho: str | os.PathLike) -> Path:
    import xlsxwriter

    caminho = Path(caminho)
    criterios, outros = colunas_template()
    wb = xlsxwriter.Workbook(str(caminho))
    f_nome = wb.add_format({"bold": True, "font_color": "#FFFFFF", "bg_color": "#B03A2E", "text_wrap": True,
                            "valign": "vcenter", "border": 1})
    f_crit = wb.add_format({"bold": True, "font_color": "#FFFFFF", "bg_color": "#123B5D", "text_wrap": True,
                            "valign": "vcenter", "border": 1})
    f_outro = wb.add_format({"bold": True, "font_color": "#123B5D", "bg_color": "#DCE8F3", "text_wrap": True,
                             "valign": "vcenter", "border": 1})
    f_ex = wb.add_format({"font_color": "#7F8C8D", "italic": True})
    f_tit = wb.add_format({"bold": True, "font_size": 16, "font_color": "#123B5D"})
    f_sub = wb.add_format({"bold": True, "font_size": 11, "font_color": "#123B5D", "bottom": 1})
    f_txt = wb.add_format({"text_wrap": True, "valign": "top"})
    f_b = wb.add_format({"bold": True, "text_wrap": True, "valign": "top"})

    ws = wb.add_worksheet("Nomes")
    ws.set_row(0, 42)
    colunas = criterios + outros
    for i, c in enumerate(colunas):
        fmt = f_nome if c == "Nome" else (f_crit if c in criterios else f_outro)
        ws.write(0, i, c, fmt)
        ws.set_column(i, i, 34 if c == "Nome" else 22)
    for r, ex in enumerate(EXEMPLOS, start=1):
        for i, c in enumerate(colunas):
            if c in ex:
                ws.write(r, i, ex[c], f_ex)
    ws.freeze_panes(1, 1)
    i_niv = colunas.index("Formação (nível)")
    ws.data_validation(1, i_niv, 5000, i_niv, {"validate": "list", "source": NIVEIS, "error_type": "information"})
    for cab in ("UF de formação", "UF / cidade de atuação"):
        j = colunas.index(cab)
        ws.data_validation(1, j, 5000, j, {"validate": "list", "source": UFS, "error_type": "information",
                                            "input_title": "UF", "input_message": "Sigla ou nome; cidade também vale"})
    ws.autofilter(0, 0, 0, len(colunas) - 1)
    for i, c in enumerate(colunas):
        crit = next((x for x in CRITERIOS if x.cabecalho == c), None)
        desc = crit.descricao if crit else ("Obrigatório." if c == "Nome" else DESCRICOES.get(c, "Compara com esta parte do currículo."))
        ws.write_comment(0, i, desc, {"x_scale": 2, "y_scale": 1.2})

    ajuda = wb.add_worksheet("Como preencher")
    ajuda.set_column(0, 0, 30)
    ajuda.set_column(1, 1, 95)
    ajuda.write(0, 0, "Busca por nomes — como preencher", f_tit)
    linhas = [
        ("Coluna Nome", "Obrigatória. Um pesquisador por linha, com o nome como aparece no Lattes (quanto mais completo, melhor)."),
        ("Demais colunas", "Opcionais. Servem de critério de desempate quando a busca encontra mais de uma pessoa com o mesmo nome. "
                           "Preencha só o que souber; células vazias são ignoradas."),
        ("Vários valores", "Separe por ponto e vírgula. Ex.: \"UFPE; USP\" aceita qualquer uma das duas."),
        ("Siglas", "Siglas e nomes por extenso funcionam (UFPE ou Universidade Federal de Pernambuco; PE ou Pernambuco)."),
        ("Colunas azul-escuras", "Critérios mais usados, comparados com o trecho certo do currículo."),
        ("Colunas azul-claras", "Qualquer outro atributo do Lattes. O texto da célula é procurado naquela parte do currículo."),
        ("Como o desempate funciona", "1) Busca o nome no CNPq. 2) Se vier só um perfil compatível, ele é escolhido. "
                                      "3) Se vierem vários, compara os critérios com o resumo de cada um. "
                                      "4) Se ainda empatar, abre o currículo completo dos melhores colocados e compara de novo. "
                                      "5) Sem vencedor claro, a linha fica como \"Ambíguo\" e todos os candidatos vão para a aba Candidatos."),
        ("Linhas de exemplo", "As duas linhas em cinza são exemplos: apague antes de usar."),
        ("Formatos aceitos", "Excel (.xlsx) ou CSV (separado por vírgula ou ponto e vírgula)."),
    ]
    for r, (a, b) in enumerate(linhas, start=2):
        ajuda.write(r, 0, a, f_b)
        ajuda.write(r, 1, b, f_txt)
        ajuda.set_row(r, 32 if len(b) > 95 else 18)

    attrs = wb.add_worksheet("Atributos")
    attrs.set_column(0, 0, 44)
    attrs.set_column(1, 1, 18)
    attrs.set_column(2, 2, 80)
    attrs.write(0, 0, "Atributos extraídos de um currículo Lattes", f_tit)
    attrs.write_row(2, 0, ["Atributo", "Uso no desempate", "Descrição"], f_sub)
    r = 3
    for c in CRITERIOS:
        attrs.write_row(r, 0, [c.cabecalho, "critério", c.descricao], f_txt)
        r += 1
    for c in COLUNAS_FIXAS + SECOES_COMUNS:
        attrs.write_row(r, 0, [c, "coluna", DESCRICOES.get(c, "Itens desta seção do currículo")], f_txt)
        r += 1
    wb.close()
    return caminho


@dataclass
class PlanilhaNomes:
    cabecalhos: list[str]
    linhas: list[dict[str, str]]
    coluna_nome: str
    criterios: list[str]            # cabeçalhos reconhecidos como critério ou coluna do CV

    def descrever_criterios(self) -> list[tuple[str, str]]:
        saida = []
        for c in self.criterios:
            alvo = identificar_coluna(c)
            if alvo and alvo[0] == "criterio":
                saida.append((c, "critério"))
            else:
                saida.append((c, "coluna do currículo"))
        return saida


def _valor(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def ler_planilha_nomes(caminho: str | os.PathLike) -> PlanilhaNomes:
    p = Path(caminho)
    if p.suffix.lower() in (".xlsx", ".xlsm"):
        import openpyxl
        wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
        ws = wb["Nomes"] if "Nomes" in wb.sheetnames else wb.worksheets[0]
        brutas = [[_valor(c) for c in row] for row in ws.iter_rows(values_only=True)]
        wb.close()
    elif p.suffix.lower() in (".csv", ".txt", ".tsv"):
        texto = p.read_bytes()
        try:
            conteudo = texto.decode("utf-8-sig")
        except UnicodeDecodeError:
            conteudo = texto.decode("cp1252")
        try:
            dialeto = csv.Sniffer().sniff(conteudo[:4096], delimiters=",;\t")
        except csv.Error:
            dialeto = csv.excel
        brutas = [[c.strip() for c in row] for row in csv.reader(conteudo.splitlines(), dialeto)]
    else:
        raise ValueError("Formato não suportado. Use .xlsx ou .csv.")

    # Cabeçalho: primeira linha com uma coluna "Nome"
    i_cab = next((i for i, row in enumerate(brutas[:20]) if any(normalizar(c) in ("nome", "nome completo", "pesquisador",
                                                                                 "nome do pesquisador") for c in row)), None)
    if i_cab is None:
        raise ValueError("Não encontrei a coluna \"Nome\". Use o template ou nomeie a coluna como Nome.")
    cab = [c or f"Coluna {j + 1}" for j, c in enumerate(brutas[i_cab])]
    col_nome = next(c for c in cab if normalizar(c) in ("nome", "nome completo", "pesquisador", "nome do pesquisador"))
    linhas = []
    # Linha de exemplo do template esquecida na planilha: só pula se for idêntica ao exemplo
    exemplos = [{k: v for k, v in e.items()} for e in EXEMPLOS]
    for row in brutas[i_cab + 1:]:
        d = {cab[j]: (row[j] if j < len(row) else "") for j in range(len(cab))}
        if not d.get(col_nome):
            continue
        preenchidos = {k: v for k, v in d.items() if v}
        if any(preenchidos == e for e in exemplos):
            continue
        linhas.append(d)
    usados = [c for c in cab if c != col_nome and any(l.get(c) for l in linhas)]
    return PlanilhaNomes(cab, linhas, col_nome, usados)

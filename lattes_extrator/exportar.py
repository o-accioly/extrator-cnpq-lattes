"""Planilhas de saída: Excel estilizado (cabeçalho, filtros, painel congelado, links,
listras) escrito em streaming, e TSV completo para Power BI."""
from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

from .texto import para_excel

LIMITE_CELULA = 32767
AVISO_CORTE = " [TRUNCADO: texto completo no .txt]"
COR_CABECALHO = "#123B5D"
COR_CABECALHO_2 = "#1E6091"
COR_LISTRA = "#F2F7FB"

LARGURAS = {
    "Nome": 34, "ID Lattes": 19, "Código CNPq": 13, "Link Lattes": 36, "ORCID": 38,
    "Assunto": 18, "Tipo da pesquisa": 18, "Status": 16, "Confiança": 11,
}


@dataclass
class Aba:
    nome: str
    colunas: list[str]
    linhas: Iterable[dict]
    congelar_colunas: int = 0
    colunas_destaque: set[str] = field(default_factory=set)   # cabeçalho em cor diferente
    larguras: dict[str, float] = field(default_factory=dict)
    cores: dict[str, dict[str, str]] = field(default_factory=dict)  # coluna -> {valor: cor de fundo}


def _largura(col: str, extras: dict[str, float]) -> float:
    if col in extras:
        return extras[col]
    if col in LARGURAS:
        return LARGURAS[col]
    if col.startswith(("Qtd.", "Contagem:", "Web of Science", "Scopus", "SciELO", "Ano ")) or "(total)" in col:
        return 13
    if col.startswith("Ocorrências"):
        return 28
    return min(48, max(14, len(col) * 0.9))


def escrever_xlsx(caminho: str | os.PathLike, abas: list[Aba]) -> dict[str, int]:
    """Escreve as abas e devolve {coluna: células cortadas} da aba "Perfis"."""
    import xlsxwriter

    wb = xlsxwriter.Workbook(str(caminho), {"constant_memory": True, "strings_to_urls": False,
                                            "strings_to_numbers": False})
    f_cab = wb.add_format({"bold": True, "font_color": "#FFFFFF", "bg_color": COR_CABECALHO,
                           "text_wrap": True, "valign": "vcenter", "border": 1,
                           "border_color": "#0B2740", "font_size": 10})
    f_cab2 = wb.add_format({"bold": True, "font_color": "#FFFFFF", "bg_color": COR_CABECALHO_2,
                            "text_wrap": True, "valign": "vcenter", "border": 1,
                            "border_color": "#0B2740", "font_size": 10})
    f_txt = wb.add_format({"font_size": 10, "valign": "top"})
    f_num = wb.add_format({"font_size": 10, "valign": "top", "num_format": "#,##0"})
    f_dec = wb.add_format({"font_size": 10, "valign": "top", "num_format": "0%"})
    f_link = wb.add_format({"font_size": 10, "valign": "top", "font_color": "#1F5FAD", "underline": 1})
    f_listra = wb.add_format({"bg_color": COR_LISTRA})

    cortes: dict[str, int] = {}
    for aba in abas:
        ws = wb.add_worksheet(aba.nome[:31])
        ws.set_row(0, 34)
        for c, col in enumerate(aba.colunas):
            ws.set_column(c, c, _largura(col, aba.larguras))
            ws.write_string(0, c, col, f_cab2 if col in aba.colunas_destaque else f_cab)
        ws.freeze_panes(1, aba.congelar_colunas)

        n = 0
        urls = 0
        for n, linha in enumerate(aba.linhas, start=1):
            for c, col in enumerate(aba.colunas):
                v = linha.get(col, "")
                if v is None or v == "":
                    continue
                if isinstance(v, bool):
                    ws.write_string(n, c, "Sim" if v else "Não", f_txt)
                elif isinstance(v, int):
                    ws.write_number(n, c, v, f_num)
                elif isinstance(v, float):
                    ws.write_number(n, c, v, f_dec if col == "Confiança" else f_num)
                else:
                    s = para_excel(str(v))
                    if s.startswith(("http://", "https://")) and len(s) < 2000 and urls < 65000 and " " not in s:
                        ws.write_url(n, c, s, f_link, string=s)
                        urls += 1
                        continue
                    if len(s) > LIMITE_CELULA:
                        s = s[: LIMITE_CELULA - len(AVISO_CORTE)] + AVISO_CORTE
                        if aba.nome == "Perfis":
                            cortes[col] = cortes.get(col, 0) + 1
                    ws.write_string(n, c, s, f_txt)
        if aba.colunas:
            ultima = len(aba.colunas) - 1
            ws.autofilter(0, 0, max(n, 1), ultima)
            if n:
                for col, mapa in aba.cores.items():
                    if col not in aba.colunas:
                        continue
                    c = aba.colunas.index(col)
                    for valor, cor in mapa.items():
                        fmt = wb.add_format({"bg_color": cor, "bold": True, "font_color": "#1B1B1B"})
                        ws.conditional_format(1, c, n, c, {"type": "cell", "criteria": "==",
                                                           "value": f'"{valor}"', "format": fmt})
                ws.conditional_format(1, 0, n, ultima, {"type": "formula", "criteria": "=MOD(ROW(),2)=0",
                                                        "format": f_listra})
    wb.close()
    return cortes


def escrever_tsv(caminho: str | os.PathLike, colunas: list[str], linhas: Iterable[dict]) -> None:
    with open(caminho, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter="\t", quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
        w.writerow(colunas)
        for linha in linhas:
            w.writerow([_tsv(linha.get(c, "")) for c in colunas])


def _tsv(v) -> str:
    if v is None:
        return ""
    return str(v).replace("\t", " ").replace("\r\n", " ").replace("\n", " ").replace("\r", " ")


class ArquivoLinhas:
    """Linhas guardadas em JSONL no disco: a memória não cresce com o número de CVs."""

    def __init__(self, caminho: str | os.PathLike) -> None:
        self.caminho = Path(caminho)
        self._f = open(self.caminho, "w", encoding="utf-8")
        self.colunas: dict[str, None] = {}
        self.total = 0

    def adicionar(self, linha: dict) -> None:
        for k in linha:
            if k not in self.colunas:
                self.colunas[k] = None
        self._f.write(json.dumps(linha, ensure_ascii=False) + "\n")
        self.total += 1

    def fechar(self) -> None:
        if not self._f.closed:
            self._f.close()

    def __iter__(self) -> Iterator[dict]:
        self.fechar()
        with open(self.caminho, encoding="utf-8") as f:
            for l in f:
                yield json.loads(l)

    def apagar(self) -> None:
        self.fechar()
        try:
            self.caminho.unlink()
        except OSError:
            pass

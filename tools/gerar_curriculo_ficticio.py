"""Gera o currículo Lattes FICTÍCIO usado nos testes e nas capturas (tests/fixtures/).

Mesma estrutura HTML da página do CNPq (classes title-wrapper, layout-cell-3/9, inst_back,
cita-artigos, artigo-completo, science_cont...), com conteúdo inventado: pessoas, instituições,
títulos e números não correspondem a ninguém. Determinístico (semente fixa): rodar de novo gera
o mesmo arquivo. A moldura da página (cabeçalho, menu e rodapé do site) vem de
tests/fixtures/moldura_lattes.html, que não tem dado pessoal.

Uso: python tools/gerar_curriculo_ficticio.py
"""
from __future__ import annotations

import html
import random
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "tests" / "fixtures" / "1234567890123456.html"
MOLDURA = RAIZ / "tests" / "fixtures" / "moldura_lattes.html"

NOME = "Ana Beatriz Exemplo Vasconcelos"
CITACOES = "VASCONCELOS, A. B. E.;Vasconcelos, Ana Beatriz Exemplo;Vasconcelos, Ana B. E.;EXEMPLO-VASCONCELOS, A. B."
CITACAO_ARTIGO = "VASCONCELOS, A. B. E."
ID16 = "1234567890123456"
KID = "K0000000A1"
ORCID = "0000-0002-1825-0097"   # ORCID de exemplo da própria documentação do ORCID
INST = "Universidade Federal de Exemplo, UFEX, Brasil"
INST_CURTA = "Universidade Federal de Exemplo"

# Quantidades usadas pelos testes (tests/test_extrator.py)
QTD = {"artigos": 120, "livros": 6, "capitulos": 30, "trab_completos": 15, "resumos_exp": 10, "resumos": 320,
       "apresentacoes": 40, "patentes": 12, "projetos_pesquisa": 25, "orient_andamento": 9, "orient_concluidas": 60}

PRENOMES = ["Lucas", "Marina", "Rafael", "Beatriz", "Thiago", "Camila", "Bruno", "Larissa", "Diego", "Fernanda",
            "Gustavo", "Juliana", "Henrique", "Patrícia", "Otávio", "Renata", "Igor", "Sabrina", "Caio", "Tatiane"]
SOBRENOMES = ["Albuquerque", "Barcelos", "Cardoso", "Damasceno", "Espíndola", "Fagundes", "Guimarães", "Holanda",
              "Ilhéus", "Junqueira", "Lacerda", "Magalhães", "Nogueira", "Oliveira", "Prado", "Queiroz", "Rezende",
              "Siqueira", "Tavares", "Uchoa", "Valadares", "Xavier", "Zanetti"]
TEMAS = ["nanopartículas lipídicas", "comprimidos de liberação prolongada", "extratos vegetais padronizados",
         "estabilidade de formulações", "canabidiol em formulações orais", "dispersões sólidas",
         "sistemas de liberação de fármacos", "controle de qualidade de insumos", "cannabis medicinal",
         "excipientes farmacêuticos", "biodisponibilidade de fármacos", "formas farmacêuticas pediátricas"]
REVISTAS = ["Revista Brasileira de Exemplo", "Journal of Example Pharmaceutics", "Acta Fictícia Farmacêutica",
            "Exemplo Pharma Reports", "Brazilian Journal of Sample Sciences"]

rnd = random.Random(20261127)


def pessoa() -> str:
    return f"{rnd.choice(PRENOMES)} {rnd.choice(SOBRENOMES)} {rnd.choice(SOBRENOMES)}"


def autor() -> str:
    p, s1, s2 = rnd.choice(PRENOMES), rnd.choice(SOBRENOMES), rnd.choice(SOBRENOMES)
    return f"{s2.upper()}, {p[0]}. {s1[0]}."


def autores(com_ela: bool = True) -> str:
    lista = [autor() for _ in range(rnd.randint(2, 6))]
    if com_ela:
        lista.insert(rnd.randrange(len(lista) + 1), f"<b>{CITACAO_ARTIGO}</b>")
    return " ; ".join(lista)


def titulo() -> str:
    return rnd.choice(["Desenvolvimento de", "Avaliação de", "Caracterização de", "Estudo de", "Otimização de"]) + \
        " " + rnd.choice(TEMAS)


e = html.escape


def par(rotulo: str, valor: str, sub: bool = False) -> str:
    cls = " subtit-1" if sub else ""
    return (f'<div class="layout-cell layout-cell-3 text-align-right{cls}"><div class="layout-cell-pad-5 text-align-right">'
            f'<b>{rotulo}</b></div></div><div class="layout-cell layout-cell-9"><div class="layout-cell-pad-5">{valor}'
            f'</div></div>')


def item(n: int, conteudo: str) -> str:
    return (f'<div class="layout-cell layout-cell-1 text-align-right"><div class="layout-cell-pad-5 text-align-right">'
            f'<b>{n}. </b></div></div><div class="layout-cell layout-cell-11"><div class="layout-cell-pad-5">'
            f'{conteudo}</div></div><br class="clear">')


def secao(ancora: str, titulo_: str, corpo: str) -> str:
    return (f'<div class="title-wrapper"><a name="{ancora}"><h1 tabindex="0">{titulo_}</h1></a><hr class="separator">'
            f'<div class="layout-cell layout-cell-12 data-cell">{corpo}</div><br class="clear"></div><br class="clear">')


def inst(nome: str) -> str:
    return f'<br class="clear"><div class="inst_back"><b>{nome}</b></div>'


def cita(nome: str, ancora: str = "") -> str:
    a = f'<a name="{ancora}"></a>' if ancora else ""
    return f'<div class="cita-artigos"><b>{a}{nome}</b></div>'


def lista(qtd: int, gerar) -> str:
    return "".join(item(i, gerar(i)) for i in range(1, qtd + 1))


def artigos(qtd: int) -> str:
    partes = []
    for i in range(1, qtd + 1):
        ano = 2025 - i // 8
        texto = (f'{autores()} . {titulo()}{" com cannabis" if i % 12 == 0 else ""}. {rnd.choice(REVISTAS)}, v. '
                 f'{rnd.randint(1, 40)}, p. {rnd.randint(1, 900)}-{rnd.randint(901, 999)}, {ano}.')
        partes.append(
            f'<div class="artigo-completo"><div class="layout-cell layout-cell-1 text-align-right">'
            f'<div class="layout-cell-pad-6 text-align-right"><b>{i}. </b></div></div>'
            f'<div class="layout-cell layout-cell-11"><span class="transform">'
            f'<span class="informacao-artigo" data-tipo-ordenacao="autor">{CITACAO_ARTIGO}</span>'
            f'<span class="informacao-artigo" data-tipo-ordenacao="ano">{ano}</span>{texto}'
            f'<span class="citado"><b class="label-citacoes">Citações:</b> {rnd.randint(0, 30)}</span>'
            f'</span></div></div>')
    return '<div id="artigos-completos">' + cita("Artigos completos publicados em periódicos", "ArtigosCompletos") + \
        "".join(partes) + "</div>"


def metrica(base: str, trabalhos: int, citacoes: int, fator: int | None) -> str:
    f = f'<div class="fator">Fator H: {fator}</div>' if fator is not None else ""
    return (f'<br class="clear"><div class="layout-cell layout-cell-12"><div class="layout-cell layout-cell-6">'
            f'<div class="layout-cell-pad"><div class="science_cont"><div class="web_s">{base}</div>'
            f'<div class="trab">Total de trabalhos: {trabalhos}</div><div class="cita">Total de citações: {citacoes}</div>'
            f'Data: 01/06/2025{f}<div class="detalhes">{CITACAO_ARTIGO}</div></div></div></div></div>')


def conteudo() -> str:
    c = []
    c.append(f'<div class="layout-cell layout-cell-3"><img class="foto" src="servletrecuperafoto?tipo=1&amp;id={KID}">'
             f'</div><div class="infpessoa"><h2 class="nome" tabindex="0">{NOME}</h2>'
             f'<h2 class="nome" tabindex="0"><span class="texto">Bolsista de Produtividade em Pesquisa do CNPq - '
             f'Nível 2</span></h2><ul class="informacoes-autor">'
             f'<li>Endereço para acessar este CV: http://lattes.cnpq.br/{ID16}</li>'
             f'<li>ID Lattes: <span style="font-weight: bold; color: #326C99;">{ID16}</span></li>'
             f'<li>Última atualização do currículo em 10/10/2026</li></ul></div><br class="clear">')
    c.append('<div class="title-wrapper"><h1 class="ui-hidden" tabindex="0"></h1><hr class="separator">'
             '<p class="resumo">Possui graduação em Farmácia pela Universidade Federal de Exemplo (1983), mestrado em '
             'Ciências Farmacêuticas (1988) e doutorado pela Université de Exemple (1992). É professora titular da '
             'Universidade Federal de Exemplo, onde coordena o Laboratório de Tecnologia Fictícia. Atua em tecnologia '
             'farmacêutica, com ênfase em sistemas de liberação de fármacos e em formulações de cannabis medicinal e '
             'canabidiol. Este currículo é fictício e serve apenas para testes do Extrator CNPq Lattes. '
             '<b>(Texto informado pelo autor)</b></p></div>')
    c.append(secao("Identificacao", "Identificação",
                   par("Nome", NOME) + par("Nome em citações bibliográficas", CITACOES)
                   + par("Lattes iD", f"http://lattes.cnpq.br/{ID16}")
                   + par("Orcid iD ", f'<a href="https://orcid.org/{ORCID}">https://orcid.org/{ORCID}</a>')
                   + par("País de Nacionalidade", "Brasil")))
    c.append(secao("Endereco", "Endereço", par(
        "Endereço Profissional", f"{INST_CURTA}, Centro de Ciências Fictícias, Departamento de Exemplos. "
        "<br>Avenida Exemplo, 1000<br>Cidade Universitária<br>00000-000 - Recife, PE - Brasil<br>"
        "Telefone: (00) 0000-0000")))
    c.append(secao("FormacaoAcademicaTitulacao", "Formação acadêmica/titulação",
                   par("1988 - 1992", "Doutorado em Ciências Farmacêuticas. <br>Université de Exemple, UEX, França. "
                       "<br>Título: Estudo fictício de granulados, Ano de obtenção: 1992. <br>Orientador: "
                       f"{pessoa()}.")
                   + par("1986 - 1988", f"Mestrado em Ciências Farmacêuticas. <br>{INST}. <br>Título: Síntese "
                         f"fictícia, Ano de Obtenção: 1988.<br>Orientador: {pessoa()}.")
                   + par("1979 - 1983", f"Graduação em Farmácia. <br>{INST}.")))
    c.append(secao("FormacaoPosDoc", "Pós-doutorado",
                   par("2012 - 2013", "Pós-Doutorado. <br>University of Example, UEXA, Estados Unidos.")))
    c.append(secao("FormacaoComplementar", "Formação Complementar",
                   lista(3, lambda i: f"Curso de {rnd.choice(TEMAS)}. (Carga horária: {8 * i}h).").replace(
                       "layout-cell-1 ", "layout-cell-3 ").replace("layout-cell-11", "layout-cell-9")))
    atu = (inst(INST) + par("Vínculo institucional", "", sub=True)
           + par("1997 - Atual", "Vínculo: Servidor Público, Enquadramento Funcional: Professora Titular, "
                 "Regime: Dedicação exclusiva.")
           + par("Outras informações", "Coordenadora do Laboratório de Tecnologia Fictícia.")
           + inst("Instituto Exemplar de Pesquisa, IEP, Brasil") + par("Vínculo institucional", "", sub=True)
           + par("2020 - Atual", "Vínculo: Colaboradora, Enquadramento Funcional: Pesquisadora visitante.")
           + inst("Agência Fictícia de Vigilância, AFV, Brasil") + par("Vínculo institucional", "", sub=True)
           + par("2011 - 2015", "Vínculo: Colaboradora, Enquadramento Funcional: Consultora."))
    c.append(secao("AtuacaoProfissional", "Atuação Profissional", atu))
    c.append(secao("LinhaPesquisa", "Linhas de pesquisa",
                   lista(3, lambda i: f"Linha fictícia {i}: {rnd.choice(TEMAS)}").replace(
                       "layout-cell-1 ", "layout-cell-3 ").replace("layout-cell-11", "layout-cell-9")))
    projetos = "".join(par(f"{2025 - i % 10} - {'Atual' if i < 5 else 2025 - i % 10 + 3}",
                           f"{titulo()}{' de cannabis' if i % 6 == 0 else ''}<br>Descrição: Projeto fictício. "
                           f"Situação: {'Em andamento' if i < 5 else 'Concluído'}; Natureza: Pesquisa.<br>"
                           f"Integrantes: {NOME} - Coordenador / {pessoa()} - Integrante.")
                       for i in range(QTD["projetos_pesquisa"]))
    c.append(secao("ProjetosPesquisa", "Projetos de pesquisa", projetos))
    c.append(secao("AreasAtuacao", "Áreas de atuação",
                   par("1.", "Grande área: Ciências da Saúde / Área: Farmácia.")
                   + par("2.", "Grande área: Ciências da Saúde / Área: Farmácia / Subárea: Farmacotécnica / "
                         "Especialidade: Tecnologia Farmacêutica.")))
    c.append(secao("Idiomas", "Idiomas", par("Inglês", "Compreende Bem, Fala Bem, Lê Bem, Escreve Bem.")
                   + par("Francês", "Compreende Razoavelmente, Fala Pouco, Lê Bem, Escreve Pouco.")))
    c.append(secao("PremiosTitulos", "Prêmios e títulos",
                   par("2025", "2º Lugar no Prêmio Fictício de Inovação Farmacêutica, Sociedade de Exemplo.")
                   + par("2019", "Menção honrosa, Congresso Fictício de Farmácia.")))
    prod = (inst("Produção bibliográfica") + '<a name="Citacoes"></a>' + cita("Citações")
            + metrica("Web of Science", 98, 1234, 18) + metrica("SciELO", 11, 7, None)
            + metrica("SCOPUS", 110, 1500, None)
            + artigos(QTD["artigos"])
            + cita("Livros publicados/organizados ou edições", "LivrosPublicadosOrganizados")
            + lista(QTD["livros"], lambda i: f"{autores()} . {titulo()}. 1. ed. Recife: Editora Fictícia, {2020 - i}.")
            + cita("Capítulos de livros publicados", "CapitulosLivrosPublicados")
            + lista(QTD["capitulos"], lambda i: f"{autores()} . {titulo()}. In: Livro de Exemplo. Recife: "
                    f"Editora Fictícia, {2024 - i // 5}, p. {i}-{i + 20}.")
            + cita("Trabalhos completos publicados em anais de congressos", "TrabalhosPublicadosAnaisCongresso")
            + lista(QTD["trab_completos"], lambda i: f"{autores()} . {titulo()}. In: Congresso Fictício, {2020 - i}.")
            + cita("Resumos expandidos publicados em anais de congressos", "ResumosExpandidosPublicadosAnaisCongressos")
            + lista(QTD["resumos_exp"], lambda i: f"{autores()} . {titulo()}. In: Simpósio de Exemplo, {2021 - i}.")
            + cita("Resumos publicados em anais de congressos", "ResumosPublicadosAnaisCongressos")
            + lista(QTD["resumos"], lambda i: f"{autores()} . {titulo()}. In: Encontro Fictício, {2025 - i // 20}.")
            + cita("Apresentações de Trabalho", "ApresentacoesTrabalho")
            + lista(QTD["apresentacoes"], lambda i: f"{autores()} . {titulo()}. {2025 - i // 8}. (Apresentação).")
            + inst("Produção técnica")
            + cita("Produtos tecnológicos", "ProdutosTecnologicos")
            + lista(4, lambda i: f"{autores()} . Produto fictício {i}. {2020 + i}.")
            + inst("Demais tipos de produção técnica")
            + cita("Trabalhos técnicos")
            + lista(3, lambda i: f"{CITACAO_ARTIGO} . Parecer técnico fictício {i}. {2015 + i}."))
    c.append(secao("ProducoesCientificas", "Produções", prod))
    c.append(secao("PatentesRegistros", "Patentes e registros",
                   cita("Patente") + lista(QTD["patentes"], lambda i: f"{autores()} . Processo fictício de obtenção "
                                           f"de {rnd.choice(TEMAS)}. {2010 + i}, Brasil.")
                   + cita("Marca registrada") + lista(1, lambda i: f"{CITACAO_ARTIGO} . Marca Fictícia. 2018.")))
    c.append(secao("PotencialInovacao", "Inovação",
                   cita("Patente") + lista(3, lambda i: f"{autores()} . Processo inovador fictício {i}. {2018 + i}.")))
    bancas = (inst("Participação em bancas de trabalhos de conclusão")
              + cita("Mestrado") + lista(14, lambda i: f"{CITACAO_ARTIGO} ; {autor()}. Participação em banca de "
                                         f"{pessoa()}. {titulo()}. {2025 - i}. Dissertação (Mestrado).")
              + cita("Teses de doutorado") + lista(8, lambda i: f"{CITACAO_ARTIGO} ; {autor()}. Participação em "
                                                 f"banca de {pessoa()}. {titulo()}. {2024 - i}. Tese (Doutorado).")
              + inst("Participação em bancas de comissões julgadoras")
              + cita("Concurso público") + lista(5, lambda i: f"{CITACAO_ARTIGO} ; {autor()}. Concurso fictício "
                                                f"para professor. {2020 - i}."))
    c.append(secao("Bancas", "Bancas", bancas))
    c.append(secao("Eventos", "Eventos", inst("Participação em eventos, congressos, exposições e feiras")
                   + lista(6, lambda i: f"Congresso Fictício de Farmácia {2019 + i}. {titulo()}. {2019 + i}. "
                                        "(Congresso).")))
    orient = (inst("Orientações e supervisões em andamento")
              + cita("Dissertação de mestrado") + lista(5, lambda i: f"{pessoa()}. {titulo()}. Início: {2024 + i % 2}. "
                                                        f"Dissertação (Mestrado) - {INST_CURTA}. (Orientador).")
              + cita("Tese de doutorado") + lista(QTD["orient_andamento"] - 5, lambda i: f"{pessoa()}. {titulo()}. "
                                                  f"Início: 2023. Tese (Doutorado) - {INST_CURTA}. (Orientador).")
              + inst("Orientações e supervisões concluídas")
              + cita("Dissertação de mestrado") + lista(35, lambda i: f"{pessoa()}. {titulo()}. {2023 - i // 3}. "
                                                         f"Dissertação (Mestrado) - {INST_CURTA}. Orientador: {NOME}.")
              + cita("Tese de doutorado") + lista(QTD["orient_concluidas"] - 35, lambda i: f"{pessoa()}. {titulo()}. "
                                                  f"{2022 - i // 3}. Tese (Doutorado) - {INST_CURTA}. Orientador: {NOME}."))
    c.append(secao("Orientacoesatividades", "Orientações", orient))
    c.append('<div class="title-wrapper"><a name="OutrasInformacoes"><h1 tabindex="0">Outras informações relevantes'
             '</h1></a><hr class="separator"><div class="layout-cell layout-cell-12 data-cell"><pre class="'
             'outras-informacoes">Pesquisadora fictícia criada para testes. Participa de redes de pesquisa em '
             'cannabis medicinal e formulações farmacêuticas.</pre></div></div>')
    return "".join(c)


def main() -> int:
    moldura = MOLDURA.read_text(encoding="utf-8")
    pagina = moldura.replace("{{CONTEUDO}}", conteudo()).replace("{{NOME}}", NOME).replace("{{KID}}", KID)
    DESTINO.write_text(pagina, encoding="utf-8")
    print(f"{DESTINO} ({len(pagina) // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

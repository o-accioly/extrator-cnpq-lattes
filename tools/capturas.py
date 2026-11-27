"""Gera capturas de tela da interface com dados de demonstração (sem rede, sem Chrome).

Uso:  QT_QPA_PLATFORM=offscreen python tools/capturas.py docs/prints
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from lattes_extrator import jobs as J  # noqa: E402
from lattes_extrator.config import Config  # noqa: E402
from lattes_extrator.gui import tema  # noqa: E402

import os
TAM = tuple(int(x) for x in os.environ.get("TAM", "1440x900").split("x"))


def processar_eventos(ms: int = 120) -> None:
    fim = time.monotonic() + ms / 1000
    while time.monotonic() < fim:
        QApplication.processEvents()
        time.sleep(0.01)


def salvar(w, destino: Path, nome: str) -> None:
    processar_eventos(450)   # espera as transições de página terminarem
    w.grab().save(str(destino / f"{nome}.png"))
    print("  ", nome)


def demo(cfg: Config, banco: J.Banco) -> None:
    fixture = RAIZ / "tests" / "fixtures" / "1234567890123456.html"
    for pasta, n in (("cannabis - Doutores", 3), ("canabidiol PE - Doutores", 2), ("Equipe UFPE - Busca por nomes", 1)):
        p = cfg.pasta_htmls / pasta
        p.mkdir(parents=True, exist_ok=True)
        for i in range(n):
            shutil.copy(fixture, p / f"{1234567890123456 + i}.html")
    agora = time.time()
    j1 = banco.criar(J.TIPO_BUSCA, "Cannabis - Doutores", {"filtros": {"texto": "cannabis"}},
                     str(cfg.pasta_htmls / "cannabis - Doutores"))
    banco.atualizar(j1.id, status=J.CONCLUIDO, total=412, feitos=409, erros=3, mensagem="409 currículos baixados")
    j2 = banco.criar(J.TIPO_NOMES, "Equipe UFPE", {}, str(cfg.pasta_htmls / "Equipe UFPE - Busca por nomes"))
    banco.atualizar(j2.id, status=J.PAUSADO, total=120, feitos=74, erros=1, mensagem="Pausada pelo usuário")
    j3 = banco.criar(J.TIPO_BUSCA, "Canabidiol - Pernambuco", {}, str(cfg.pasta_htmls / "canabidiol PE - Doutores"))
    banco.atualizar(j3.id, status=J.CANCELADO, total=193, feitos=58, mensagem="Interrompida pelo usuário")
    j4 = banco.criar(J.TIPO_PROCESSAR, "Compilação geral", {})
    banco.atualizar(j4.id, status=J.CONCLUIDO, total=467, feitos=467, mensagem="467 perfis em 31s")
    banco._con.execute("UPDATE jobs SET atualizado = atualizado - 86400*2 WHERE id = ?", (j4.id,))
    banco._con.execute("UPDATE jobs SET atualizado = ? WHERE id = ?", (agora - 3600 * 5, j1.id))
    (cfg.pasta_planilhas / "Cannabis - Doutores - 409 perfis.xlsx").write_bytes(b"")
    # Currículos extras (opcional) para a base ter variedade nas capturas: DEMO_HTMLS=pasta
    extra = os.environ.get("DEMO_HTMLS")
    if extra:
        for f in Path(extra).rglob("*.html"):
            destino = cfg.pasta_htmls / f.parent.name
            destino.mkdir(parents=True, exist_ok=True)
            shutil.copy(f, destino / f.name)
    nomes = cfg.raiz / "nomes.csv"
    nomes.write_text("Nome;Formação (nível);Instituição onde trabalha;UF / cidade de atuação;Palavras-chave\n"
                     "Ana Beatriz Exemplo Vasconcelos;Doutorado;UFEX;PE;cannabis\n"
                     "Maria da Silva Santos;Doutorado;Universidade Federal da Bahia;BA;\n"
                     "João Pereira da Silva;Mestrado;;SP;enfermagem\n"
                     "Ana Paula Ferreira Lima;Doutorado;USP;SP;canabidiol\n"
                     "Carlos Eduardo Souza;Graduação;;RJ;\n", encoding="utf-8")


def main() -> int:
    destino = Path(sys.argv[1] if len(sys.argv) > 1 else RAIZ / "docs" / "prints")
    destino.mkdir(parents=True, exist_ok=True)
    from lattes_extrator.gui.app import preparar_webengine
    preparar_webengine()
    app = QApplication(sys.argv)
    tema.aplicar(app)
    tmp = Path(tempfile.mkdtemp(prefix="lattes-demo-"))
    cfg = Config(pasta_trabalho=str(tmp), mostrar_intro=False)
    cfg.garantir_pastas()
    banco = J.Banco(cfg.banco)
    demo(cfg, banco)
    banco.fechar()

    print("Intro:")
    from lattes_extrator.gui.intro import Intro
    intro = Intro()
    intro.resize(*TAM)
    intro.show()
    for ms, nome in ((450, "01-intro-chuva"), (1700, "02-intro-decodificando"), (3300, "03-intro-titulo"),
                     (4800, "04-intro-final")):
        intro.quadro_em(ms)
        salvar(intro, destino, nome)
    intro.close()

    from lattes_extrator import diagnostico as D
    from lattes_extrator.gui.diagnostico import DialogoDiagnostico
    from lattes_extrator.gui.janela import JanelaPrincipal
    # verificação do ambiente determinística: sem rede e sem a thread do programa de verdade
    JanelaPrincipal.verificar_ambiente = lambda self: None
    jan = JanelaPrincipal(cfg)
    jan.resize(*TAM)
    jan.show()
    diag_ok = D.executar(cfg, rede=False)
    for c in diag_ok.checagens:   # caminhos desta máquina não vão para as capturas públicas
        if c.nome == "Arquivos do programa":
            c.detalhe = "lattes_extrator/data"
        if c.nome == "Google Chrome":
            c.detalhe = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
    diag_ruim = D.Resultado([c for c in diag_ok.checagens])
    diag_ruim.checagens[2] = D.Checagem(
        "Automação do Chrome (Selenium)", D.ERRO,
        "Não carregou: selenium.webdriver.chrome.options (ModuleNotFoundError)",
        "O executável está incompleto. Baixe a versão mais recente do programa.", (D.COLETA, D.NOMES))
    diag_ruim.checagens.append(D.Checagem("Acesso ao CNPq", D.AVISO, "Sem resposta de buscatextual.cnpq.br",
                                          "Confira a internet ou o proxy/firewall.", (D.COLETA, D.NOMES)))
    print("Páginas:")
    jan._ambiente_verificado(diag_ok)
    jan.ir("inicio")
    salvar(jan, destino, "10-inicio")
    jan._ambiente_verificado(diag_ruim)
    salvar(jan, destino, "11-inicio-problema-no-ambiente")
    dlg = DialogoDiagnostico(cfg, diag_ruim, jan)
    dlg.resize(min(760, TAM[0] - 80), min(680, TAM[1] - 60))
    dlg.show()
    salvar(dlg, destino, "72-verificacao-do-ambiente")
    dlg.close()
    jan._ambiente_verificado(diag_ok)

    jan.abrir_assistente("busca")
    salvar(jan, destino, "20-busca-como-funciona")
    a = jan.paginas["busca"]
    a.cnpq.texto.setText("cannabis")
    a.cnpq.f.formacao_nivel = "Doutorado"
    a.cnpq.f.formacao_uf = "PE"
    a.cnpq.f.atuacao_grande_area = "40000001"
    a.cnpq.f.idioma = "EN"
    a.cnpq.c_demais.setChecked(True)
    a.cnpq._atualizar_caixas()
    a.ir_passo(1)
    salvar(jan, destino, "21-busca-filtros-cnpq")
    from lattes_extrator.gui.filtros_cnpq import FAtuacao, FFormacao, ModalFiltro
    for cls, nome in ((FFormacao, "22-busca-filtro-formacao"), (FAtuacao, "23-busca-filtro-area")):
        dlg = ModalFiltro(cls.titulo, jan)
        flt = cls(a.cnpq)
        f = a.cnpq.f.copia(atuacao_area="40300005", atuacao_subarea="40301001")
        flt.montar(dlg, f)
        dlg.resize(620, dlg.sizeHint().height())
        dlg.show()
        salvar(dlg, destino, nome)
        dlg.close()
    a.ir_passo(2)
    salvar(jan, destino, "24-busca-opcoes")
    a.ir_passo(3)
    salvar(jan, destino, "25-busca-revisao")

    jan.abrir_assistente("nomes")
    salvar(jan, destino, "30-nomes-como-funciona")
    n = jan.paginas["nomes"]
    n.ir_passo(1)
    n.carregar(str(cfg.raiz / "nomes.csv"))
    salvar(jan, destino, "31-nomes-planilha")
    n.ir_passo(2)
    salvar(jan, destino, "32-nomes-filtros")
    n.ir_passo(3)
    salvar(jan, destino, "33-nomes-opcoes")
    n.ir_passo(4)
    salvar(jan, destino, "34-nomes-revisao")

    jan.abrir_assistente("processar")
    p = jan.paginas["processar"]
    p.ir_passo(1)
    salvar(jan, destino, "40-processar-pastas")

    print("Base:")
    jan.ir("base")
    pb = jan.paginas["base"]
    if pb.indexador:
        pb.indexador.wait(60000)
    processar_eventos(600)
    salvar(jan, destino, "45-base")
    pb.e_busca.setText("canabidiol")
    pb.c_ordem.setCurrentIndex(0)
    pb.pesquisar()
    salvar(jan, destino, "46-base-busca")
    pb.abrir_perfil()
    salvar(jan, destino, "47-perfil-geral")
    pp = jan.paginas["perfil"]
    pp.abas.setCurrentIndex(1)
    salvar(jan, destino, "48-perfil-secoes")
    pp.abas.setCurrentIndex(2)
    processar_eventos(4000)   # o motor web carrega a página e os estilos locais
    salvar(jan, destino, "49-perfil-original")

    # Execução simulada (sem thread)
    pg = jan.paginas["execucao"]
    banco2 = jan.banco
    job = banco2.criar(J.TIPO_BUSCA, "Cannabis - Pernambuco", {}, str(cfg.pasta_htmls / "cannabis - Doutores"))
    banco2.atualizar(job.id, status=J.RODANDO, total=193)
    pg.job_id = job.id
    pg._estado(True)
    pg.pill.definir("Em andamento", tema.VERDE, pulsar=True)
    pg.spinner.iniciar()
    pg.barra.ativo = True
    pg.b_pausa.show()
    pg.b_parar.show()
    pg.b_cont.hide()
    logs = [("Abrindo o Chrome…", "info"), ("Buscando no CNPq", "etapa"),
            ("193 currículos encontrados.", "ok"), ("Página 1 de 2 · 100 perfis", "etapa")]
    nomes_demo = ["Lucas Albuquerque Prado", "Marina Fagundes Rezende", "Rafael Damasceno Xavier",
                  "Ana Beatriz Exemplo Vasconcelos", "Camila Holanda Siqueira", "Bruno Lacerda Tavares",
                  "Juliana Nogueira Zanetti"]
    for i, nm in enumerate(nomes_demo):
        logs.append((f"Baixando {nm} (K000000{i}A1)", "info"))
        logs.append((f"{nm} → 12345678901234{i:02d}.html", "ok"))
    logs.insert(9, ("O CNPq pediu verificação (currículo). Resolva o captcha na janela do Chrome.", "aviso"))
    logs.insert(10, ("Verificação concluída, continuando.", "ok"))
    logs.append(("Bruno Lacerda Tavares: A janela do currículo não abriu.", "erro"))
    logs.append(("72/193 processados · 11/min · memória 182 MB", "debug"))
    for m, nv in logs:
        pg.log.adicionar(m, nv)
    pg._etapa("Página 1 de 2 · 100 perfis")
    pg._progresso({"feitos": 72, "total": 193, "erros": 1, "taxa": 11.4, "eta": "10m37s", "decorrido": "6m18s",
                   "memoria": 182.0, "detalhe": "Juliana Nogueira Zanetti"})
    pg.barra.setValue(int(72 / 193 * 1000))
    pg._brilho = 0.6
    jan.ir("execucao")
    salvar(jan, destino, "50-execucao")
    pg.banner.mostrar("O CNPq pediu verificação (currículo). Resolva o captcha na janela do Chrome.  "
                      "A extração continua sozinha assim que a verificação for concluída.")
    salvar(jan, destino, "51-execucao-captcha")
    pg.banner.hide()
    banco2.atualizar(job.id, status=J.CONCLUIDO, total=193, feitos=192, erros=1, mensagem="Coleta concluída",
                     saida=str(cfg.pasta_planilhas / "Cannabis - Doutores - 409 perfis.xlsx"))
    pg.terminou()
    pg._progresso({"feitos": 193, "total": 193, "erros": 1, "taxa": 12.1, "eta": "—", "decorrido": "16m02s",
                   "memoria": 190.0, "detalhe": ""})
    pg.barra.setValue(1000)
    processar_eventos(700)
    salvar(jan, destino, "52-execucao-concluida")

    jan.ir("extracoes")
    jan.paginas["extracoes"].tab.selectRow(1)
    salvar(jan, destino, "60-extracoes")
    jan.ir("config")
    salvar(jan, destino, "70-configuracoes")
    jan.banco.fechar()
    shutil.rmtree(tmp, ignore_errors=True)
    QTimer.singleShot(0, app.quit)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Controle do Chrome (Selenium) no site de busca do CNPq.

Tudo acontece num Chrome de verdade, visível, no ritmo de uma pessoa:

* a busca é feita no próprio formulário do site (o site monta a consulta e roda o
  reCAPTCHA invisível dele);
* o currículo é aberto pelo botão "Currículo Lattes" da janela de detalhes, como um
  clique humano;
* se o CNPq pedir para resolver um captcha, o programa avisa e espera a pessoa
  resolver na janela do Chrome. Ele não tenta resolver captcha sozinho.
"""
from __future__ import annotations

import base64
import random
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field

import lxml.html

from .config import Config
from .eventos import Controle, Reporter
from .filtros import JS_PREENCHER, FiltrosBusca
from .texto import decodificar_html, limpar

BASE = "https://buscatextual.cnpq.br/buscatextual/"
URL_BUSCA = BASE + "busca.do?metodo=apresentar"
URL_PREVIEW = BASE + "preview.do?metodo=apresentar&id={}"

RE_KID_HREF = re.compile(r"abreDetalhe\('([A-Za-z0-9]{10})'")
RE_TOTAL = re.compile(r"d[eo]s?\s+([\d.]+)\s+encontrad", re.I)
RE_FAIXA = re.compile(r"Resultados?\s+de\s+([\d.]+)\s*-\s*([\d.]+)", re.I)
RE_ID16 = re.compile(r"lattes\.cnpq\.br/(?:240\.1/)?(\d{16})")

JS_CAPTCHA_VISIVEL = r"""
const ifr = [...document.querySelectorAll('iframe[src*="recaptcha"]')];
const vis = ifr.some(f => { const r = f.getBoundingClientRect(), s = getComputedStyle(f);
  return r.width > 100 && r.height >= 70 && s.visibility !== 'hidden' && s.display !== 'none'; });
const div = document.getElementById('divCaptcha');
const divVis = div && div.offsetParent !== null && div.childElementCount > 0;
return vis || !!divVis;
"""

JS_BAIXAR = r"""
const url = arguments[0], fim = arguments[arguments.length - 1];
fetch(url, {credentials: 'include'}).then(r => r.arrayBuffer()).then(buf => {
  const b = new Uint8Array(buf); let s = '';
  for (let i = 0; i < b.length; i += 0x8000) s += String.fromCharCode.apply(null, b.subarray(i, i + 0x8000));
  fim(btoa(s));
}).catch(e => fim('ERRO:' + e));
"""


class ErroNavegador(Exception):
    pass


class ListagemComErro(ErroNavegador):
    """O CNPq respondeu "N encontrados" mas trocou os perfis por uma mensagem de erro do
    servidor (ex.: ``<li>Stale file handle</li>``). É intermitente: refazer resolve."""


# Esperas (s) entre as tentativas quando a listagem vem com erro do servidor
ESPERAS_LISTAGEM = (3, 10, 30)


@dataclass
class Candidato:
    """Um resultado da listagem de busca."""
    kid: str
    nome: str
    resumo: str = ""                  # linha da listagem (titulação, vínculo)
    preview: dict = field(default_factory=dict)

    def texto_leve(self) -> str:
        p = self.preview
        return " ".join(x for x in (self.resumo, p.get("resumo", ""), p.get("bolsa", "")) if x)


def faixa_listagem(html: str) -> tuple[int, int]:
    """(primeiro, último) resultado mostrados na página, numerados a partir de 1."""
    doc = lxml.html.fromstring(html)
    tit = limpar(" ".join(doc.xpath('//div[contains(@class,"tit_form")]//text()')))
    m = RE_FAIXA.search(tit)
    if not m:
        return 0, 0
    return int(m.group(1).replace(".", "")), int(m.group(2).replace(".", ""))


def parse_listagem(html: str) -> tuple[int, list[Candidato]]:
    doc = lxml.html.fromstring(html)
    tit = " ".join(doc.xpath('//div[contains(@class,"tit_form")]//text()'))
    m = RE_TOTAL.search(limpar(tit))
    total = int(m.group(1).replace(".", "")) if m else 0
    cands: list[Candidato] = []
    for li in doc.xpath('//div[contains(@class,"resultado")]//ol/li'):
        links = li.xpath(".//b/a[@href]") or li.xpath(".//a[contains(@href,'abreDetalhe')]")
        if not links:
            continue
        m = RE_KID_HREF.search(links[0].get("href", ""))
        if not m:
            continue
        nome = limpar(links[0].text_content())
        texto = limpar(" ".join(li.itertext()))
        resumo = texto[len(nome):].strip() if texto.startswith(nome) else texto
        cands.append(Candidato(m.group(1), nome, resumo))
    if not total and cands:
        total = len(cands)
    return total, cands


def erro_listagem(html: str) -> str:
    """Texto dos itens da listagem que não são perfis (mensagem de erro do servidor no
    lugar do resultado). Vazio quando a listagem está normal."""
    doc = lxml.html.fromstring(html)
    itens = {limpar(" ".join(li.itertext())) for li in doc.xpath('//div[contains(@class,"resultado")]//ol/li')
             if not li.xpath(".//a[contains(@href,'abreDetalhe')]")}
    return "; ".join(sorted(i for i in itens if i))[:200]


def parse_preview(html: str) -> dict:
    doc = lxml.html.fromstring(html)
    nome = limpar(" ".join(doc.xpath('//h1[contains(@class,"name")]//text()')))
    resumo = limpar(" ".join(doc.xpath('//p[contains(@class,"resumo")]//text()')))
    texto = limpar(" ".join(doc.xpath("//text()[not(ancestor::script) and not(ancestor::style)]")))
    m = re.search(r"Certificado pelo autor em\s*(\d{2}/\d{2}/\d{4})", texto)
    m16 = RE_ID16.search(html)
    bolsa = ""
    mb = re.search(r"(Bolsista de Produtividade[^.]*?(?:Nível|N[íi]vel)?\s*\w{1,2})\b", texto)
    if mb:
        bolsa = mb.group(1)
    return {"nome": nome, "resumo": resumo, "atualizado": m.group(1) if m else "",
            "id16": m16.group(1) if m16 else "", "bolsa": bolsa}


class NavegadorLattes:
    def __init__(self, cfg: Config, reporter: Reporter, controle: Controle) -> None:
        self.cfg = cfg
        self.rep = reporter
        self.ctl = controle
        self.driver = None
        self.por_pagina = cfg.resultados_por_pagina
        self.inicio_pagina = 0
        self._aba_busca = None

    # ------------------------------------------------------------------ ciclo
    def abrir(self) -> None:
        # Caminhos completos de propósito: o ``selenium.webdriver`` carrega ``ChromeOptions``/``Chrome``
        # sob demanda (importlib), e o PyInstaller não enxerga esses módulos se o import for indireto.
        try:
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.chrome.webdriver import WebDriver
        except ImportError as e:
            raise ErroNavegador(f"A automação do Chrome (Selenium) não carregou: {e}. "
                                "Atualize o programa para a versão mais recente.") from e
        opts = Options()
        opts.add_argument("--start-maximized")
        opts.add_argument("--lang=pt-BR")
        opts.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        opts.add_experimental_option("useAutomationExtension", False)
        if self.cfg.chrome_perfil_persistente:
            self.cfg.perfil_chrome.mkdir(parents=True, exist_ok=True)
            opts.add_argument(f"--user-data-dir={self.cfg.perfil_chrome}")
        self.rep.log("Abrindo o Chrome…")
        try:
            # Executável sem console no Windows: sem a flag, o chromedriver abre uma janela preta.
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform.startswith("win") else 0
            # Selenium Manager baixa o driver certo para o Chrome instalado
            self.driver = WebDriver(options=opts, service=Service(popen_kw={"creation_flags": flags}))
        except Exception as e:
            msg = str(e).splitlines()[0]
            if "user data directory is already in use" in str(e):
                msg = "o perfil do Chrome do extrator já está aberto em outra janela. Feche-a e tente de novo."
            raise ErroNavegador(f"Não foi possível abrir o Chrome: {msg}") from e
        self.driver.set_page_load_timeout(max(30, self.cfg.timeout_pagina * 2))
        self._aba_busca = self.driver.current_window_handle

    def fechar(self) -> None:
        if self.driver is not None:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

    def __enter__(self) -> "NavegadorLattes":
        self.abrir()
        return self

    def __exit__(self, *exc) -> None:
        self.fechar()

    # --------------------------------------------------------------- utilidades
    def _esperar(self, condicao, timeout: float | None = None, intervalo: float = 0.3):
        """Espera ``condicao()`` ficar verdadeira, respeitando pausa/cancelamento."""
        fim = time.monotonic() + (timeout or self.cfg.timeout_pagina)
        while time.monotonic() < fim:
            self.ctl.checar()
            try:
                r = condicao()
                if r:
                    return r
            except Exception:
                pass
            time.sleep(intervalo)
        return None

    def _pausa_humana(self, base: float) -> None:
        self.ctl.dormir(max(0.5, base * random.uniform(0.7, 1.3)))

    def captcha_visivel(self) -> bool:
        try:
            return bool(self.driver.execute_script(JS_CAPTCHA_VISIVEL))
        except Exception:
            return False

    def aguardar_captcha(self, contexto: str) -> None:
        """Se houver captcha visível, avisa e espera a pessoa resolver no Chrome."""
        if not self.captcha_visivel():
            return
        self.rep.aguardando_usuario(f"O CNPq pediu verificação ({contexto}). Resolva o captcha na janela do Chrome.")
        ultimo_bip = 0.0
        while self.captcha_visivel():
            self.ctl.checar()
            if self.cfg.alerta_sonoro and time.monotonic() - ultimo_bip > 15:
                _bip()
                ultimo_bip = time.monotonic()
            time.sleep(1)
        self.rep.log("Verificação concluída, continuando.", "ok")

    def _baixar_mesma_origem(self, url: str) -> str:
        """GET feito pela própria página (mesma origem e cookies do navegador)."""
        self.driver.set_script_timeout(self.cfg.timeout_pagina)
        r = self.driver.execute_async_script(JS_BAIXAR, url)
        if not r or str(r).startswith("ERRO:"):
            raise ErroNavegador(f"falha ao ler {url}: {r}")
        return decodificar_html(base64.b64decode(r))

    # ------------------------------------------------------------------ busca
    def buscar(self, filtros: FiltrosBusca) -> int:
        """Abre a busca, preenche o formulário e clica em Buscar. Devolve o total."""
        return self._listagem_valida(lambda: self._buscar_uma_vez(filtros), "na busca")

    def _listagem_valida(self, carregar, contexto: str) -> int:
        """Roda ``carregar`` (busca ou troca de página) e confere a listagem. Se o CNPq disser
        que achou perfis mas não mostrar nenhum, espera, confere de novo (pode ter sido só
        demora) e refaz; depois de todas as tentativas levanta ``ListagemComErro``, que vira
        falha do item, e não "não encontrado"."""
        d = self.driver
        for tentativa in range(len(ESPERAS_LISTAGEM) + 1):
            total = carregar()
            if not total or self.candidatos_da_pagina():
                return total
            # pode ser só a lista terminando de aparecer: confere mais uma vez antes de refazer
            if self._esperar(lambda: bool(self.candidatos_da_pagina()), timeout=3):
                return total
            erro = erro_listagem(d.page_source) or "listagem sem perfis"
            if tentativa == len(ESPERAS_LISTAGEM):
                raise ListagemComErro(f"o site do CNPq devolveu a listagem com erro ({erro}) {contexto}, "
                                      f"em {tentativa + 1} tentativas. Tente continuar mais tarde.")
            espera = ESPERAS_LISTAGEM[tentativa]
            self.rep.log(f"O site do CNPq devolveu a listagem com erro ({erro}); tentando de novo em {espera}s "
                         f"({tentativa + 1}/{len(ESPERAS_LISTAGEM)}).", "aviso")
            self.ctl.dormir(espera)
        return 0  # inalcançável

    def _buscar_uma_vez(self, filtros: FiltrosBusca) -> int:
        d = self.driver
        d.switch_to.window(self._aba_busca)
        d.get(URL_BUSCA)
        if not self._esperar(lambda: d.execute_script("return !!document.getElementById('botaoBuscaFiltros')")):
            raise ErroNavegador("A página de busca do CNPq não carregou.")
        dados = filtros.para_formulario(self.por_pagina)
        faltando = d.execute_script(JS_PREENCHER, dados)
        if faltando:
            self.rep.log("Campos não encontrados no formulário do CNPq (o site pode ter mudado): "
                         + ", ".join(faltando), "aviso")
        antigo = d.find_element("id", "botaoBuscaFiltros")
        antigo.click()
        self.inicio_pagina = 0
        total = self._aguardar_listagem(antigo)
        self._ajustar_tamanho_pagina(total)
        return total

    def _ajustar_tamanho_pagina(self, total: int) -> None:
        """O CNPq nem sempre respeita "resultados por página". Mede o tamanho real e,
        se vier menor que o pedido, pede de novo pela paginação do próprio site."""
        d = self.driver
        ini, fim = faixa_listagem(d.page_source)
        real = (fim - ini + 1) if ini else len(self.candidatos_da_pagina())
        desejado = self.cfg.resultados_por_pagina
        if real and real < desejado and total > real and d.execute_script(
                "return typeof submeterPaginacao === 'function'"):
            antigo = d.find_element("css selector", ".resultado")
            d.execute_script("submeterPaginacao(0, arguments[0])", desejado)
            self._aguardar_listagem(antigo)
            ini, fim = faixa_listagem(d.page_source)
            real = (fim - ini + 1) if ini else len(self.candidatos_da_pagina())
        self.por_pagina = max(1, real or desejado)

    def _aguardar_listagem(self, elemento_antigo=None) -> int:
        d = self.driver

        def pronto():
            if elemento_antigo is not None:
                try:
                    elemento_antigo.is_enabled()
                    return False          # ainda na página anterior
                except Exception:
                    pass
            if d.execute_script("return document.readyState") != "complete":
                return False
            return d.execute_script(
                "return !!document.querySelector('.resultado') || /Nenhum resultado/i.test(document.body.innerText)")

        if not self._esperar(pronto, timeout=self.cfg.timeout_pagina * 2):
            self.aguardar_captcha("busca")
            if not self._esperar(pronto, timeout=self.cfg.timeout_pagina):
                raise ErroNavegador("A listagem de resultados não apareceu.")
        total, _ = parse_listagem(d.page_source)
        return total

    def candidatos_da_pagina(self) -> list[Candidato]:
        _, cands = parse_listagem(self.driver.page_source)
        return cands

    def proxima_pagina(self, total: int) -> bool:
        prox = self.inicio_pagina + self.por_pagina
        if prox >= total:
            return False
        d = self.driver
        d.switch_to.window(self._aba_busca)
        if not d.execute_script("return typeof submeterPaginacao === 'function'"):
            raise ErroNavegador("Paginação do CNPq não encontrada (o site pode ter mudado).")

        def trocar() -> int:
            antigo = d.find_element("css selector", ".resultado")
            d.execute_script("submeterPaginacao(arguments[0], arguments[1])", prox, self.por_pagina)
            self._aguardar_listagem(antigo)
            return total

        self._listagem_valida(trocar, f"na página a partir do resultado {prox + 1}")
        ini, _ = faixa_listagem(d.page_source)
        self.inicio_pagina = ini - 1 if ini else prox
        if ini and ini - 1 != prox:
            raise ErroNavegador(f"Paginação inesperada: pedi a partir de {prox + 1}, veio {ini}.")
        return True

    def recarregar(self) -> None:
        self.driver.refresh()
        self._aguardar_listagem()

    # ---------------------------------------------------------------- perfis
    def preview(self, kid: str) -> dict:
        """Dados da janela de detalhes (não pede captcha): resumo, atualização, ID16."""
        self.driver.switch_to.window(self._aba_busca)
        return parse_preview(self._baixar_mesma_origem(URL_PREVIEW.format(kid)))

    def baixar_cv(self, kid: str) -> str:
        """Abre o currículo completo pelo botão do site e devolve o HTML."""
        d = self.driver
        d.switch_to.window(self._aba_busca)
        antes = set(d.window_handles)
        d.switch_to.new_window("tab")
        aba_preview = d.current_window_handle
        try:
            d.get(URL_PREVIEW.format(kid))
            botao = self._esperar(lambda: d.find_element("css selector", "a[onclick*='abreCV']"))
            if not botao:
                raise ErroNavegador("Botão 'Currículo Lattes' não encontrado na janela de detalhes.")
            botao.click()

            def aba_cv():
                novas = [h for h in d.window_handles if h not in antes and h != aba_preview]
                if novas:
                    return novas[-1]
                return aba_preview if "visualizacv" in d.current_url else None

            alvo = self._esperar(aba_cv, timeout=self.cfg.timeout_pagina)
            if not alvo:
                self.aguardar_captcha("abrir currículo")
                alvo = self._esperar(aba_cv, timeout=self.cfg.timeout_pagina)
            if not alvo:
                raise ErroNavegador("A janela do currículo não abriu.")
            d.switch_to.window(alvo)

            def carregado():
                return d.execute_script(
                    "return document.readyState === 'complete' && !!document.querySelector('div.infpessoa h2.nome')")

            if not self._esperar(carregado, timeout=self.cfg.timeout_pagina):
                self.aguardar_captcha("currículo")
                if not self._esperar(carregado, timeout=self.cfg.timeout_pagina * 2):
                    raise ErroNavegador("O currículo não carregou (tempo esgotado).")
            time.sleep(0.8)  # o Lattes ainda injeta alguns blocos via JS
            return d.page_source
        finally:
            for h in list(d.window_handles):
                if h not in antes:
                    try:
                        d.switch_to.window(h)
                        d.close()
                    except Exception:
                        pass
            d.switch_to.window(self._aba_busca)


def _bip() -> None:
    try:
        import winsound
        winsound.Beep(1000, 400)
    except Exception:
        print("\a", end="", flush=True)


def extrair_id16(html: str) -> str:
    m = re.search(r"ID Lattes:\s*(?:<[^>]+>\s*)*(\d{16})", html)
    if m:
        return m.group(1)
    m = re.search(r"acessar este CV:\s*https?://lattes\.cnpq\.br/(\d{16})", html)
    return m.group(1) if m else ""

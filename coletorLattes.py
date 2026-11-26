#!/usr/bin/python
# encoding: utf-8

import time
import os
import re
import sys
import datetime
import winsound
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# --- CONFIGURAÇÕES ---
DELAY_ENTRE_CURRICULOS = 5  # Segundos entre uma extração e outra
TIMEOUT_PADRAO = 20         # Tempo máximo de espera genérico
TIMEOUT_CARREGAMENTO_CURRICULO = 20 # Tempo máximo para carregar a página do CV
TIMEOUT_MODAL = 5           # Tempo máximo para o modal de detalhes aparecer
ESPERA_LISTA_VAZIA = 300     # Tempo de espera se a lista sumir (bloqueio)
PASTA_HTMLS = "htmls"       # Onde serão salvos os currículos
ALERTA_SONORO_FREQ = 1000   # Frequência do som de alerta (Hz)
ALERTA_SONORO_DUR = 500     # Duração do som de alerta (ms)
INTERVALO_ALERTA = 10       # Intervalo entre alertas de captcha (s)
# ---------------------

def criar_pasta_se_nao_existir(caminho):
    if not os.path.exists(caminho):
        os.makedirs(caminho)

def tocar_alerta():
    winsound.Beep(ALERTA_SONORO_FREQ, ALERTA_SONORO_DUR)

def tratar_captcha(driver):
    """
    Verifica se há captcha e tenta resolver com Buster ou alerta o usuário.
    """
    try:
        # O reCAPTCHA geralmente fica dentro de um iframe
        # Primeiro verificamos se o iframe de 'checkbox' está presente
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        captcha_presente = False
        for iframe in iframes:
            try:
                # Verifica se o iframe está visível
                if not iframe.is_displayed():
                    continue
                src = iframe.get_attribute("src")
                if "google.com/recaptcha" in src:
                    captcha_presente = True
                    break
            except:
                continue
        
        if not captcha_presente:
            return

        print("[AVISO] Captcha visível detectado!")
        
        while True:
            # Verifica se ainda há captcha visível na página
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            ainda_tem_captcha = False
            for iframe in iframes:
                try:
                    if not iframe.is_displayed():
                        continue
                    src = iframe.get_attribute("src")
                    if "google.com/recaptcha" in src:
                        ainda_tem_captcha = True
                        # Tenta procurar o botão do Buster se estivermos no iframe correto
                        # O Buster costuma injetar botões em iframes específicos do reCAPTCHA
                        # Mas como ele é uma extensão, às vezes é melhor tentar clicar via CSS global se possível
                        # O seletor fornecido pelo usuário foi .help-button-holder
                        try:
                            # Tenta clicar no buster se estiver visível no contexto atual
                            buster = driver.find_element(By.CSS_SELECTOR, ".help-button-holder")
                            if buster.is_displayed():
                                buster.click()
                                print("[INFO] Botão do Buster clicado.")
                                time.sleep(5)
                        except:
                            pass
                except:
                    continue
            
            if not ainda_tem_captcha:
                print("[INFO] Captcha não detectado.")
                break
                
            print(f"[ALERTA] Resolva o captcha manualmente. Próximo alerta em {INTERVALO_ALERTA}s.")
            tocar_alerta()
            time.sleep(INTERVALO_ALERTA)
            
    except Exception as e:
        print(f"[ERRO ao tratar captcha] {e}")

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    print("Erro: As bibliotecas 'selenium' e 'webdriver-manager' são necessárias.")
    print("Instale-as com: pip install selenium webdriver-manager")
    sys.exit(1)

def extrair_ids(html):
    # IDs Lattes podem ter 10 ou 16 dígitos
    # Frequentemente aparecem em links como id=... ou lattes.cnpq.br/1234567890123456
    ids = set()
    
    # Busca por padrões de 16 dígitos ou 10 dígitos, priorizando 16 para não capturar sub-strings
    # Usamos lookahead/lookbehind ou limites de palavra se possível, 
    # mas no HTML o separador pode ser aspas, igual, ou barra.
    
    # Busca por 16 dígitos
    patterns16 = [
        r'id=(\d{16})',
        r'lattes\.cnpq\.br/(\d{16})',
        r'idbusca=(\d{16})',
        r"abreDetalhe\('(\w{10,16})'"
    ]
    
    # Busca por 10 dígitos (apenas se não fizer parte de um de 16)
    patterns10 = [
        r'id=(\d{10})(?!\d)',
        r'lattes\.cnpq\.br/(\d{10})(?!\d)',
        r'idbusca=(\d{10})(?!\d)',
        r"abreDetalhe\('(\w{10})'"
    ]
    
    for pattern in patterns16:
        matches = re.findall(pattern, html)
        for m in matches:
            ids.add(m)

    for pattern in patterns10:
        matches = re.findall(pattern, html)
        for m in matches:
            ids.add(m)
            
    return ids

def gerar_config(nome_grupo, arquivo_list):
    config_template = f"""# ---------------------------------------------------------------------------- #
# scriptLattes - Arquivo gerado automaticamente pelo Coletor                    #
# ---------------------------------------------------------------------------- #
global-nome_do_grupo       = {nome_grupo}
global-arquivo_de_entrada  = {arquivo_list}
global-diretorio_de_saida  = ./resultados/{nome_grupo}/
global-email_do_admin      = admin@email.com
global-idioma              = PT
global-itens_desde_o_ano   = 
global-itens_ate_o_ano     = 
global-itens_por_pagina    = 5000

# RELATÓRIOS DE PRODUÇÃO
relatorio-incluir_artigo_em_periodico                  = sim
relatorio-incluir_livro_publicado                      = sim
relatorio-incluir_capitulo_de_livro_publicado          = sim
relatorio-incluir_texto_em_jornal_de_noticia           = sim
relatorio-incluir_trabalho_completo_em_congresso       = sim
relatorio-incluir_resumo_expandido_em_congresso        = sim
relatorio-incluir_resumo_em_congresso                  = sim
relatorio-incluir_artigo_aceito_para_publicacao        = sim
relatorio-incluir_apresentacao_de_trabalho             = sim
relatorio-incluir_outro_tipo_de_producao_bibliografica = sim

relatorio-incluir_software_com_registro                = sim
relatorio-incluir_software_sem_registro                = sim
relatorio-incluir_produto_tecnologico                  = sim
relatorio-incluir_processo_ou_tecnica                  = sim
relatorio-incluir_trabalho_tecnico                     = sim
relatorio-incluir_outro_tipo_de_producao_tecnica       = sim
relatorio-incluir_entrevista_mesas_e_comentarios       = sim

relatorio-incluir_producao_artistica                   = sim

# RELATÓRIOS DE ORIENTAÇÕES
relatorio-mostrar_orientacoes                                          = sim
relatorio-incluir_orientacao_em_andamento_pos_doutorado                = sim
relatorio-incluir_orientacao_em_andamento_doutorado                    = sim
relatorio-incluir_orientacao_em_andamento_mestrado                     = sim
relatorio-incluir_orientacao_em_andamento_monografia_de_especializacao = sim
relatorio-incluir_orientacao_em_andamento_tcc                          = sim
relatorio-incluir_orientacao_em_andamento_iniciacao_cientifica         = sim
relatorio-incluir_orientacao_em_andamento_outro_tipo                   = sim

relatorio-incluir_orientacao_concluida_pos_doutorado                   = sim
relatorio-incluir_orientacao_concluida_doutorado                       = sim
relatorio-incluir_orientacao_concluida_mestrado                        = sim
relatorio-incluir_orientacao_concluida_monografia_de_especializacao    = sim
relatorio-incluir_orientacao_concluida_tcc                             = sim
relatorio-incluir_orientacao_concluida_iniciacao_cientifica            = sim
relatorio-incluir_orientacao_concluida_outro_tipo                      = sim

# RELATÓRIOS ADICIONAIS
relatorio-incluir_projeto                = sim
relatorio-incluir_premio                 = sim
relatorio-incluir_participacao_em_evento = sim
relatorio-incluir_organizacao_de_evento  = sim

# GRAFO DE COLABORAÇÕES
grafo-mostrar_grafo_de_colaboracoes                         = sim
grafo-mostrar_todos_os_nos_do_grafo                         = sim
grafo-considerar_rotulos_dos_membros_do_grupo               = nao

grafo-incluir_artigo_em_periodico                           = sim
grafo-incluir_livro_publicado                               = sim
grafo-incluir_capitulo_de_livro_publicado                   = sim
grafo-incluir_texto_em_jornal_de_noticia                    = sim
grafo-incluir_trabalho_completo_em_congresso                = sim
grafo-incluir_resumo_expandido_em_congresso                 = sim
grafo-incluir_resumo_em_congresso                           = sim
grafo-incluir_artigo_aceito_para_publicacao                 = sim
grafo-incluir_apresentacao_de_trabalho                      = sim
grafo-incluir_outro_tipo_de_producao_bibliografica          = sim

grafo-incluir_software_com_registro                         = sim
grafo-incluir_software_sem_registro                         = sim
grafo-incluir_produto_tecnologico                           = sim
grafo-incluir_processo_ou_tecnica                           = sim
grafo-incluir_trabalho_tecnico                              = sim
grafo-incluir_outro_tipo_de_producao_tecnica                = sim
grafo-incluir_entrevista_mesas_e_comentarios                = sim

grafo-incluir_producao_artistica                            = sim

relatorio-incluir_metricas           = sim
"""
    return config_template

def logger(mensagem, arquivo_log=None):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg_formatada = f"[{timestamp}] {mensagem}"
    print(msg_formatada)
    if arquivo_log:
        try:
            with open(arquivo_log, "a", encoding="utf-8") as f:
                f.write(msg_formatada + "\n")
        except:
            pass

def extrair_id16(html_cv):
    """
    Extrai o ID de 16 dígitos do HTML do currículo.
    """
    # Tenta encontrar no link do Lattes (formato padrão)
    match = re.search(r'http://lattes.cnpq.br/(\d{16})', html_cv)
    if match:
        return match.group(1)
    
    # Fallback: procurar em outros lugares se necessário
    # No HTML do Lattes, o ID costuma aparecer em vários lugares
    return None

def iniciar_coleta():
    assunto = input("Digite o assunto (ex: meu_assunto): ").strip()
    if not assunto:
        assunto = "assunto_coletado"
    
    print("\nEscolha a base:")
    print("1 - Doutores")
    print("2 - Demais pesquisadores")
    opcao_base = input("Opção (1 ou 2): ").strip()
    
    if opcao_base == "2":
        categoria = "Demais pesquisadores"
    else:
        categoria = "Doutores"
    
    nome_grupo = assunto # Mantemos nome_grupo para compatibilidade com o resto do código
    subpasta_htmls = os.path.join(PASTA_HTMLS, f"{assunto} - {categoria}")
    criar_pasta_se_nao_existir(subpasta_htmls)

    arquivo_list = f"{nome_grupo}.list"
    arquivo_config = f"{nome_grupo}.config"
    arquivo_log = f"{nome_grupo}.log"
    
    logger(f"--- INICIANDO COLETA PARA O GRUPO: {nome_grupo} ---", arquivo_log)
    logger(f"IDs serão salvos em: {arquivo_list}", arquivo_log)
    logger(f"Logs salvos em: {arquivo_log}", arquivo_log)
    
    print("\nO Chrome será aberto. Navegue no site do Lattes (busca, listas, etc.)")
    print("O script coletará automaticamente os IDs Lattes encontrados nas páginas que você visitar.")
    print("Pressione Ctrl+C no terminal para encerrar a coleta.\n")

    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("start-maximized")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    
    try:
        driver_path = ChromeDriverManager().install()
        service = Service(driver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e:
        logger(f"Erro ao abrir o Chrome: {e}", arquivo_log)
        return

    ids_coletados = set()
    
    # Se o arquivo já existir, carregar IDs para evitar duplicatas
    if os.path.exists(arquivo_list):
        with open(arquivo_list, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line: continue
                part = line.split(':')
                if len(part) > 1:
                    ids_coletados.add(part[1])
                else:
                    ids_coletados.add(line)
        logger(f"Retomando de onde parou. {len(ids_coletados)} IDs já conhecidos.", arquivo_log)

    pagina_atual = 1
    perfil_numero = 0
    contador_vazio = 0

    try:
        driver.get("https://buscatextual.cnpq.br/buscatextual/busca.do")
        print("Aguardando você realizar a busca e chegar na tela de resultados...")
        
        while True:
            # Verifica se há listagem de resultados na tela
            try:
                # Busca rápida para ver se os itens da lista existem
                itens_lista = driver.find_elements(By.CSS_SELECTOR, ".resultado ol li")
                tem_listagem = len(itens_lista) > 0
                
                # Verifica se há paginação (links de números ou 'próximo')
                paginacao_links = driver.find_elements(By.CSS_SELECTOR, "a[data-role='paginacao']")
                tem_paginacao = len(paginacao_links) > 0
            except:
                tem_listagem = False
                tem_paginacao = False

            if not tem_listagem:
                # Se já iniciamos a coleta (perfil_numero > 0) e a lista sumiu, mas a paginação 
                # ou outros elementos ainda existem, pode ser um bloqueio de conteúdo.
                if perfil_numero > 0:
                    contador_vazio += 1
                    # Se persistir por 5 verificações (aprox 10s)
                    if contador_vazio >= 5:
                        logger(f"[AVISO] Listagem vazia detectada na página {pagina_atual}. Possível bloqueio do site.", arquivo_log)
                        logger(f"Aguardando {ESPERA_LISTA_VAZIA} segundos antes de recarregar a página...", arquivo_log)
                        
                        tempo_esperado = 0
                        while tempo_esperado < ESPERA_LISTA_VAZIA:
                            tratar_captcha(driver)
                            time.sleep(10)
                            tempo_esperado += 10
                        
                        logger("Recarregando a página para tentar retomar a listagem...", arquivo_log)
                        driver.refresh()
                        time.sleep(5)
                        contador_vazio = 0
                        continue
                
                # Se não tem listagem, verifica se há um captcha VISÍVEL bloqueando
                tratar_captcha(driver)
                # Aguarda um pouco e tenta novamente
                time.sleep(2)
                continue

            # Se chegamos aqui, a listagem foi detectada. Reseta contador de vazio.
            contador_vazio = 0
            # Tenta identificar a página atual pela UI
            try:
                elem_pag = driver.find_element(By.CSS_SELECTOR, "a[data-role='paginacao'] font[color='#ff0000']")
                pagina_atual = int(elem_pag.text)
            except:
                pass

            # Podemos re-verificar o captcha por precaução (caso apareça sobre a lista)
            tratar_captcha(driver)

            wait = WebDriverWait(driver, TIMEOUT_PADRAO)
            # Obtém todos os itens da lista na página atual
            itens = driver.find_elements(By.CSS_SELECTOR, ".resultado ol li")
            logger(f"Listagem detectada na página {pagina_atual}. Processando {len(itens)} itens.", arquivo_log)

            # Guarda a janela principal da lista antes de começar o processamento
            janela_lista = driver.current_window_handle

            for i in range(len(itens)):
                perfil_numero += 1
                # Recarregar os itens para evitar StaleElementReferenceException
                itens = driver.find_elements(By.CSS_SELECTOR, ".resultado ol li")
                item = itens[i]
                
                try:
                    link_nome = item.find_element(By.CSS_SELECTOR, "b a")
                    nome_pesquisador = link_nome.text
                    href = link_nome.get_attribute("href") # javascript:abreDetalhe('ID',...)
                    
                    # Extrair ID do href
                    match = re.search(r"abreDetalhe\('(\w+)'", href)
                    if not match:
                        continue
                    
                    id_lattes = match.group(1)
                    
                    # Verifica se o ID (seja 10 ou 16) já foi extraído
                    ja_extraido = False
                    if id_lattes in ids_coletados:
                        ja_extraido = True
                    else:
                        # Se tivermos o ID de 10 caracteres, mas no arquivo temos o de 16
                        # precisamos abrir o currículo para descobrir o ID de 16 e comparar.
                        # Para otimizar, se o arquivo .html já existir com o ID de 10, consideramos extraído.
                        if os.path.exists(os.path.join(subpasta_htmls, f"{id_lattes}.html")):
                             ja_extraido = True
                    
                    if ja_extraido:
                        logger(f"[PULANDO] Perfil {perfil_numero} - {nome_pesquisador} ({id_lattes}) já extraído.", arquivo_log)
                        continue

                    logger(f"Extraindo perfil {perfil_numero} - {nome_pesquisador} ({id_lattes})...", arquivo_log)
                    
                    # Clica para abrir o detalhe (modal)
                    driver.execute_script("arguments[0].click();", link_nome)
                    
                    # Lista de seletores possíveis para o botão de abrir currículo no modal
                    seletores_cv = [
                        (By.CSS_SELECTOR, "ul.m-isntituicoes li:first-child a"),
                        (By.ID, "idbtnabrircurriculo"),
                        (By.XPATH, "//a[contains(., 'Currículo Lattes')]"),
                        (By.XPATH, "//a[contains(., 'Abrir Currículo')]")
                    ]
                    
                    btn_cv = None
                    for tentativa in range(2): # Duas tentativas de abrir o modal se necessário
                        for by, selector in seletores_cv:
                            try:
                                # Usamos o timeout específico do modal para cada seletor
                                elemento = WebDriverWait(driver, TIMEOUT_MODAL).until(EC.visibility_of_element_located((by, selector)))
                                if elemento:
                                    btn_cv = elemento
                                    break
                            except:
                                continue
                        
                        if btn_cv:
                            break
                        
                        if tentativa == 0:
                            driver.execute_script("arguments[0].click();", link_nome)
                            time.sleep(2)

                    if not btn_cv:
                        raise Exception("Não foi possível localizar o botão para abrir o currículo no modal.")
                    
                    driver.execute_script("arguments[0].click();", btn_cv)
                    
                    # Lattes abre em nova aba/janela
                    wait.until(lambda d: len(d.window_handles) > 1)
                    
                    # Muda para a nova janela
                    for handle in driver.window_handles:
                        if handle != janela_lista:
                            driver.switch_to.window(handle)
                            break
                    
                    # Espera o currículo carregar
                    try:
                        # Espera por elementos que indicam que o conteúdo principal foi carregado.
                        # .title-wrapper contém os títulos das seções (Formação, Atuação, etc.)
                        # .layout-cell-pad-5 contém o texto dentro das seções.
                        # Esperamos pelo menos um desses estar visível.
                        WebDriverWait(driver, TIMEOUT_CARREGAMENTO_CURRICULO).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, ".title-wrapper, .layout-cell-pad-5, .artigo-completo"))
                        )
                        # Adiciona uma espera extra de segurança para garantir que o JS terminou de renderizar tudo
                        time.sleep(2) 
                    except:
                        # Se falhar o wait, ainda tenta esperar um pouco
                        time.sleep(3)
                    
                    # Salva o HTML
                    html_cv = driver.page_source
                    
                    # Extrai o ID de 16 dígitos
                    id16 = extrair_id16(html_cv)
                    if id16:
                        logger(f"ID 16 dígitos extraído: {id16}", arquivo_log)
                        id_para_salvar = id16
                    else:
                        logger(f"[AVISO] Não foi possível extrair o ID de 16 dígitos para {nome_pesquisador}. Usando ID da listagem ({id_lattes}).", arquivo_log)
                        id_para_salvar = id_lattes

                    caminho_arquivo = os.path.join(subpasta_htmls, f"{id_para_salvar}.html")
                    with open(caminho_arquivo, "w", encoding='utf-8') as f_html:
                        f_html.write(html_cv)
                    
                    # Adiciona à lista de coletados
                    if id_para_salvar not in ids_coletados:
                        ids_coletados.add(id_para_salvar)
                        with open(arquivo_list, 'a', encoding='utf-8') as f:
                            f.write(f"{len(ids_coletados)}:{id_para_salvar}\n")
                    
                    logger(f"Perfil {perfil_numero} extraído com sucesso: {id_para_salvar}.html", arquivo_log)
                    
                    # Fecha a janela do currículo e volta para a lista
                    driver.close()
                    driver.switch_to.window(janela_lista)
                    
                    # Espera um pouco para não ser bloqueado
                    time.sleep(DELAY_ENTRE_CURRICULOS)
                    
                    # Fecha o modal de detalhes
                    try:
                        fechar_detalhe = driver.find_elements(By.XPATH, "//input[@value='Fechar' or @value='fechar']")
                        if fechar_detalhe:
                            fechar_detalhe[0].click()
                    except:
                        pass

                except Exception as e:
                    logger(f"[ERRO no perfil {perfil_numero}] {e}", arquivo_log)
                    # Se tivermos mais de uma janela, precisamos fechar as novas e voltar para a principal
                    handles = driver.window_handles
                    if len(handles) > 1:
                        for h in handles:
                            if h != janela_lista:
                                try:
                                    driver.switch_to.window(h)
                                    driver.close()
                                except:
                                    pass
                    try:
                        driver.switch_to.window(janela_lista)
                    except:
                        pass
                    continue

            # --- PAGINAÇÃO ---
            try:
                paginacao = driver.find_elements(By.CSS_SELECTOR, "a[data-role='paginacao']")
                
                proximo_clique = None
                proximo_numero_str = str(pagina_atual + 1)
                
                for link in paginacao:
                    if link.text.strip() == proximo_numero_str:
                        proximo_clique = link
                        break
                
                if not proximo_clique:
                    for link in paginacao:
                        if "próximo" in link.text.lower():
                            proximo_clique = link
                            break
                
                if proximo_clique:
                    logger(f"Paginando para a aba {pagina_atual + 1}...", arquivo_log)
                    driver.execute_script("arguments[0].click();", proximo_clique)
                    pagina_atual += 1
                    time.sleep(5) # Espera carregar a nova página
                else:
                    logger("Fim da listagem. Nenhuma opção de próxima página encontrada.", arquivo_log)
                    break
            except Exception as e:
                logger(f"[ERRO na paginação] {e}", arquivo_log)
                break

    except KeyboardInterrupt:
        logger("[COLETA ENCERRADA PELO USUÁRIO]", arquivo_log)
    except Exception as e:
        logger(f"[ERRO CRÍTICO DURANTE COLETA] {e}", arquivo_log)
    finally:
        # Salvar arquivo de configuração
        try:
            with open(arquivo_config, 'w', encoding='utf-8') as f:
                f.write(gerar_config(nome_grupo, arquivo_list))
            
            logger("\n--- RESUMO DA COLETA ---", arquivo_log)
            logger(f"- Total de IDs coletados: {len(ids_coletados)}", arquivo_log)
            logger(f"- Arquivo de lista: {arquivo_list}", arquivo_log)
            logger(f"- Arquivo de configuração: {arquivo_config}", arquivo_log)
            logger(f"- Arquivo de log: {arquivo_log}", arquivo_log)
            
            print("\nVocê já pode rodar o scriptLattes com:")
            print(f"python scriptLattes.py {arquivo_config}")
        except Exception as e:
            print(f"Erro ao salvar arquivos finais: {e}")
        
        try:
            driver.quit()
        except:
            pass

if __name__ == "__main__":
    iniciar_coleta()

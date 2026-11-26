import os
import re
import pandas as pd
from bs4 import BeautifulSoup
import glob
from tqdm import tqdm
from collections import Counter
import unicodedata
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
import ftfy

# =============================================================================
# REGEX GLOBAIS PARA PERFORMANCE
# =============================================================================

# Caracteres proibidos ou problemáticos no XML do Excel (00-08, 0B-0C, 0E-1F, 7F-9F, etc)
# XML 1.0 permite apenas 09 (tab), 0A (newline), 0D (carriage return).
# Adicionamos surrogates e non-characters para segurança total.
CONTROL_CHARS_PATTERN = re.compile(
    r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]|'
    r'[\ud800-\udfff]|'
    r'[\ufffe\uffff]'
)

# Outros padrões pré-compilados
WHITESPACE_PATTERN = re.compile(r'\s+')
COLUMN_CLEANUP_PATTERN = re.compile(r'[^\w\s\(\):-]')

# Opções do ftfy usadas em todo o extrator. NFC (e não NFKC) para não alterar dados:
# NFKC troca 'º'/'ª' por 'o'/'a', '²' por '2', etc.
FTFY_OPCOES = dict(
    normalization='NFC',
    uncurl_quotes=True,
    fix_entities=True,
    remove_terminal_escapes=True,
    fix_encoding=True,
    fix_latin_ligatures=True,
    fix_character_width=True,
)

# Palavras-chave contadas em cada currículo. Comparação sem acento e em minúsculas.
# Termos longos casam como trecho (pega plurais: "canabinoides"); siglas curtas só como
# palavra inteira, para "cbd"/"thc" não casarem no meio de outras palavras.
PALAVRAS_CHAVE = [
    'cannabis', 'cannabidiol', 'canabidiol', 'canhamo', 'canabinologia',
    'tetrahidrocanabinol', 'canabinoide', 'cannabinoid', 'cbd', 'thc',
]
SIGLAS_PALAVRA_INTEIRA = {'cbd', 'thc'}
PADROES_PALAVRAS_CHAVE = {
    pc: re.compile(rf'\b{re.escape(pc)}\b' if pc in SIGLAS_PALAVRA_INTEIRA else re.escape(pc))
    for pc in PALAVRAS_CHAVE
}

def remover_acentos(txt):
    if not txt:
        return ""
    # Normaliza para NFD e remove marcas de acentuação (Mn)
    return "".join(c for c in unicodedata.normalize('NFD', txt)
                  if unicodedata.category(c) != 'Mn')

def reparar_mojibake(txt):
    """
    Repara mojibake (UTF-8 lido como Latin-1) usando ftfy com configurações agressivas.
    ftfy é a biblioteca padrão ouro para correção de texto corrompido.
    """
    if not isinstance(txt, str) or not txt:
        return txt

    return ftfy.fix_text(txt, **FTFY_OPCOES)

def limpar_caracteres_invalidos(txt):
    """Remove caracteres de controle e NULL bytes que quebram o Excel (XML)."""
    if not isinstance(txt, str) or not txt:
        return txt

    # 1. Repara encoding corrompido (Mojibake) com ftfy agressivo
    txt = ftfy.fix_text(txt, **FTFY_OPCOES)

    # 2. Normaliza quebras de linha para o padrão que o Excel prefere (\n)
    txt = txt.replace('\r\n', '\n').replace('\r', '\n')

    # 3. Remove caracteres proibidos no XML do Excel usando Regex
    return CONTROL_CHARS_PATTERN.sub('', txt)

def normalizar_nome_coluna(nome):
    """Normaliza nomes de colunas para evitar caracteres estranhos no Excel/CSV."""
    if not isinstance(nome, str):
        return nome
    
    # 1. Limpa caracteres inválidos e repara encoding
    nome = limpar_caracteres_invalidos(nome)
    
    # 2. Remove acentos APENAS para o nome da coluna (para compatibilidade máxima)
    nome = remover_acentos(nome)
    
    # 3. Substitui caracteres especiais por sublinhado, mantendo letras, números, espaços, parênteses, dois-pontos e hífens
    nome = COLUMN_CLEANUP_PATTERN.sub('_', nome)
    
    # 4. Limpa espaços duplos e quebras de linha que podem estar no nome da coluna
    nome = WHITESPACE_PATTERN.sub(' ', nome).strip()
    return nome

def extrair_nome_rapido(soup):
    """Extrai apenas o nome do pesquisador usando BeautifulSoup."""
    # Tenta no h2 (nome em destaque)
    title_tag = soup.find('h2')
    if title_tag:
        nome = title_tag.get_text().strip()
        if nome and 'CNPq' not in nome:
            return nome

    # Tenta no title do head
    header_title = soup.find('title')
    if header_title:
        name_match = re.search(r'\((.*?)\)', header_title.get_text())
        if name_match:
            return name_match.group(1).strip()

    return "Nome não encontrado"

def extrair_dados_lattes(soup, html_content, file_id):
    """
    Extrai dados do Lattes recebendo o soup já pronto (evita re-parsing).
    """
    # 1. ESTÁGIO INICIAL: Identificação Básica
    dados = {
        'ID Lattes': file_id,
        'Nome': '',
        'País de Nacionalidade': '',
        'Endereço Profissional': '',
        'Data de Atualização': '',
        'Resumo': '',
        'Outras informações relevantes': '',
        'Produção Bibliográfica (Total)': 0
    }

    # Nome - Geralmente no título ou h2
    title_tag = soup.find('h2')
    if title_tag:
        dados['Nome'] = title_tag.get_text().strip()
    
    # Se não achou no h2, tenta no title do head
    if not dados['Nome'] or 'CNPq' in dados['Nome']:
        header_title = soup.find('title')
        if header_title:
            name_match = re.search(r'\((.*?)\)', header_title.get_text())
            if name_match:
                dados['Nome'] = name_match.group(1)

    # Data de Atualização
    at_search = soup.find(string=re.compile(r'Última atualização do currículo em', re.I))
    if at_search:
        dados['Data de Atualização'] = at_search.split('em')[-1].strip()

    # Resumo
    resumo_tag = soup.find(['p', 'div'], class_='resumo')
    if resumo_tag:
        dados['Resumo'] = resumo_tag.get_text().strip()
    else:
        resumo_header = soup.find(['h1', 'h2', 'b'], string=re.compile(r'Resumo', re.I))
        if resumo_header:
            parent = resumo_header.find_parent('div', class_='title-wrapper')
            if parent:
                res_cell = parent.find('div', class_='layout-cell-12')
                if res_cell:
                    dados['Resumo'] = res_cell.get_text().strip()
                else:
                    next_div = parent.find_next_sibling('div')
                    if next_div:
                        dados['Resumo'] = next_div.get_text().strip()

    # País de Nacionalidade
    pais_tag = soup.find('div', string=re.compile(r'País de Nacionalidade', re.I))
    if pais_tag:
        pais_val = pais_tag.find_next_sibling('div', class_='layout-cell-9')
        if pais_val:
            dados['País de Nacionalidade'] = pais_val.get_text(strip=True)

    # Endereço Profissional
    end_tag = soup.find('div', string=re.compile(r'Endereço Profissional', re.I))
    if end_tag:
        end_val = end_tag.find_next_sibling('div', class_='layout-cell-9')
        if end_val:
            dados['Endereço Profissional'] = end_val.get_text(separator=' ', strip=True)

    # Outras informações relevantes
    outras_info_pre = soup.find('pre', class_='outras-informacoes')
    if outras_info_pre:
        dados['Outras informações relevantes'] = outras_info_pre.get_text(strip=True)

    # 2. ESTÁGIO DE EXTRAÇÃO DINÂMICA
    
    # Funções auxiliares de extração
    def extrair_atuacao_profissional():
        anchor = soup.find('a', attrs={'name': re.compile(r'AtuacaoProfissional|Atuação profissional', re.I)})
        if not anchor:
            anchor = soup.find(['h1', 'h2', 'b'], string=re.compile(r'AtuacaoProfissional|Atuação profissional', re.I))
        
        if not anchor: return ""

        content_div = anchor.find_parent('div', class_='title-wrapper')
        if not content_div: return ""

        # Usar um dicionário para agrupar por instituição como solicitado
        atuacoes_dict = {}
        
        # Encontrar todas as seções de instituição
        inst_divs = content_div.find_all('div', class_='inst_back')
        
        # Se não encontrou inst_back dentro do content_div, tenta buscar nos irmãos seguintes
        if not inst_divs:
            curr = content_div.find_next_sibling()
            while curr and not (curr.name == 'div' and 'title-wrapper' in curr.get('class', [])) and curr.name != 'h1':
                inst_divs.extend(curr.find_all('div', class_='inst_back'))
                curr = curr.find_next_sibling()

        for inst_div in inst_divs:
            inst_nome = inst_div.get_text(strip=True)
            if not inst_nome: continue
            
            # Limpa o nome da instituição
            inst_nome = re.sub(r'\s+', ' ', inst_nome).strip()
            
            vinculos = []
            # O container pai da instituição geralmente contém os vínculos
            parent_cell = inst_div.find_parent('div', class_='layout-cell-12')
            if parent_cell:
                p3s = parent_cell.find_all('div', class_='layout-cell-3')
                p9s = parent_cell.find_all('div', class_='layout-cell-9')
                
                for p3, p9 in zip(p3s, p9s):
                    periodo = p3.get_text(strip=True)
                    descricao = p9.get_text(strip=True)
                    
                    # Limpeza de espaços extras
                    periodo = re.sub(r'\s+', ' ', periodo).strip()
                    descricao = re.sub(r'\s+', ' ', descricao).strip()
                    
                    if periodo and descricao and periodo != "Vínculo institucional":
                        vinculos.append(f"{periodo}: {descricao}")
                    elif descricao and descricao != "Vínculo institucional":
                        vinculos.append(descricao)
            
            if inst_nome in atuacoes_dict:
                atuacoes_dict[inst_nome].extend([v for v in vinculos if v not in atuacoes_dict[inst_nome]])
            else:
                atuacoes_dict[inst_nome] = vinculos

        # O usuário pediu um dicionário como "resultado final", mas para o DataFrame 
        # precisamos de uma representação em string legível.
        # Vou retornar a string formatada que representa esse dicionário.
        if not atuacoes_dict:
            return ""
            
        return " | ".join([f"{inst}: [{'; '.join(vinc)}]" for inst, vinc in atuacoes_dict.items()])

    def extrair_secoes_dinamicas():
        secoes_encontradas = {}
        
        # A. Extração via 'cita-artigos'
        divs_cita = soup.find_all('div', class_='cita-artigos')
        for div in divs_cita:
            titulo_tag = div.find('b')
            titulo = titulo_tag.get_text(strip=True) if titulo_tag else div.get_text(strip=True)
            if not titulo: continue
            
            # Limpeza básica do título da seção já na extração
            titulo = WHITESPACE_PATTERN.sub(' ', titulo).strip()
                
            items = []
            capturados = []  # elementos já lidos aqui, removidos do soup depois
            curr = div.find_next_sibling()
            while curr:
                classes = curr.get('class', []) if curr.name == 'div' else []
                if 'cita-artigos' in classes or 'inst_back' in classes or 'title-wrapper' in classes:
                    break
                if 'artigo-completo' in classes or (curr.name == 'div' and 'layout-cell-11' in classes):
                    capturados.append(curr)
                if 'artigo-completo' in classes:
                    # Artigos em periódicos vêm em <div class="artigo-completo">, com o texto
                    # dentro de um layout-cell-11 que não é irmão direto do cabeçalho.
                    cell = curr.find('div', class_='layout-cell-11')
                    if cell:
                        # Remove spans ocultos de ordenação (autor/ano duplicados) e o bloco de citações
                        for oculto in cell.select('span.informacao-artigo, span.citado'):
                            oculto.decompose()
                        text = WHITESPACE_PATTERN.sub(' ', cell.get_text(separator=' ', strip=True))
                        if text and text not in items: items.append(text)
                elif curr.name == 'div' and 'layout-cell-11' in classes:
                    text = curr.get_text(separator=' ', strip=True)
                    if text:
                        text = WHITESPACE_PATTERN.sub(' ', text)
                        if text not in items: items.append(text)
                curr = curr.find_next_sibling()
            
            if items:
                if titulo in secoes_encontradas:
                    for it in items:
                        if it not in secoes_encontradas[titulo]: secoes_encontradas[titulo].append(it)
                else:
                    secoes_encontradas[titulo] = items
                # Remove do soup o que já virou coluna aqui. Sem isso, a seção-mãe
                # ("Produções", "Bancas", "Orientações"...) lida no passo B repetia
                # todo o conteúdo das subseções numa coluna gigante, cortada no Excel.
                for elem in capturados:
                    elem.decompose()
                div.decompose()

        # B. Extração via 'title-wrapper'
        wrappers = soup.find_all('div', class_='title-wrapper')
        for wrapper in wrappers:
            h1 = wrapper.find('h1')
            if not h1 or not h1.get_text(strip=True): continue
            
            titulo = h1.get_text(strip=True)
            # Limpeza básica do título da seção já na extração
            titulo = WHITESPACE_PATTERN.sub(' ', titulo).strip()
            
            items = []
            targets = [wrapper]
            curr = wrapper.find_next_sibling()
            while curr and not (curr.name == 'div' and 'title-wrapper' in curr.get('class', [])) and curr.name != 'h1':
                targets.append(curr)
                curr = curr.find_next_sibling()

            for target in targets:
                data_cells = target.find_all('div', class_='layout-cell-12') if target.name != 'div' or 'layout-cell-12' not in target.get('class', []) else [target]
                for cell in data_cells:
                    pairs_3 = cell.find_all('div', class_='layout-cell-3')
                    pairs_9 = cell.find_all('div', class_='layout-cell-9')
                    
                    if pairs_3 and pairs_9:
                        for p3, p9 in zip(pairs_3, pairs_9):
                            t3 = p3.get_text(separator=' ', strip=True)
                            t9 = p9.get_text(separator=' ', strip=True)
                            if t3 and t9: items.append(f"{t3}: {t9}")
                            elif t9: items.append(t9)
                    else:
                        text_blocks = cell.get_text(separator='\n', strip=True).split('\n')
                        for block in text_blocks:
                            clean_block = WHITESPACE_PATTERN.sub(' ', block).strip()
                            if len(clean_block) > 10: items.append(clean_block)

            if items:
                seen = set()
                final_items = [it for it in items if not (it in seen or seen.add(it))]
                if titulo in secoes_encontradas:
                    for it in final_items:
                        if it not in secoes_encontradas[titulo]: secoes_encontradas[titulo].append(it)
                else:
                    secoes_encontradas[titulo] = final_items
        
        # Retorna também a quantidade de itens por seção: contar pelo texto unido não funciona,
        # porque o próprio separador ' ; ' aparece entre os autores de cada citação.
        textos = {k: ' ; '.join(v) for k, v in secoes_encontradas.items()}
        contagens = {k: len(v) for k, v in secoes_encontradas.items()}
        return textos, contagens

    # Texto visível para a contagem de palavras-chave. Calculado aqui porque a extração
    # dinâmica remove elementos do soup. Ignora script/style, atributos e marcação,
    # que antes inflavam a contagem.
    texto_visivel = ' '.join(
        s for s in soup.find_all(string=True)
        if s.parent is not None and s.parent.name not in ('script', 'style', 'noscript', 'head', 'title')
    )

    # Executa extração dinâmica
    dados['Atuação Profissional'] = extrair_atuacao_profissional()
    secoes_dinamicas, contagem_itens = extrair_secoes_dinamicas()
    dados.update(secoes_dinamicas)

    # 3. ESTÁGIO DE CÁLCULOS TOTAIS
    chaves_producao = [
        'Artigos completos publicados em periódicos',
        'Livros publicados',
        'Capítulos de livros publicados',
        'Trabalhos completos publicados em anais de congressos',
        'Livros publicados/organizados ou edições'
    ]
    total_prod = 0
    for k in chaves_producao:
        total_prod += contagem_itens.get(k, 0)
    dados['Produção Bibliográfica (Total)'] = total_prod

    # 4. ESTÁGIO DE PALAVRAS-CHAVE (Sempre por último)
    # Normaliza o conteúdo UMA VEZ para todas as palavras-chave (otimização crítica)
    content_normalizado = remover_acentos(texto_visivel).lower()

    # Colunas de texto já extraídas, normalizadas uma vez (sem as colunas de palavras-chave)
    colunas_normalizadas = {
        col: remover_acentos(valor).lower()
        for col, valor in dados.items()
        if col not in ('ID Lattes', 'Nome') and isinstance(valor, str)
    }

    for pc, padrao in PADROES_PALAVRAS_CHAVE.items():
        contagem = len(padrao.findall(content_normalizado))

        # Ocorrências em colunas
        colunas_encontradas = [col for col, valor in colunas_normalizadas.items() if padrao.search(valor)]

        dados[f'Contagem: {pc}'] = contagem
        dados[f'Ocorrências (Colunas): {pc}'] = ' ; '.join(colunas_encontradas)

    return dados

def processar_um_arquivo(arquivo, pasta_htmls):
    """Função worker para processar um único arquivo em paralelo."""
    file_id = os.path.basename(arquivo).replace('.html', '')
    
    # Lógica de Assunto e Tipo da Pesquisa baseada na pasta
    parent_dir = os.path.dirname(arquivo)
    folder_name = os.path.basename(parent_dir)
    
    assunto = ""
    tipo_pesquisa = ""
    
    if folder_name and folder_name != os.path.basename(pasta_htmls):
        if " - " in folder_name:
            partes = folder_name.split(" - ", 1)
            assunto = partes[0].strip()
            tipo_pesquisa = partes[1].strip()
        elif " " in folder_name:
            partes = folder_name.split(" ", 1)
            assunto = partes[0].strip()
            tipo_pesquisa = partes[1].strip()
        else:
            assunto = folder_name
    
    try:
        # Lê o arquivo em modo binário
        with open(arquivo, 'rb') as f:
            raw_content = f.read()

        # Detecta encoding a partir do próprio HTML (meta charset)
        content = None

        # Primeiro, tenta extrair o charset declarado no HTML
        charset_match = re.search(
            rb'<meta[^>]+charset=["\']?([^"\'>\s]+)',
            raw_content[:2000],  # Busca apenas no início do arquivo
            re.I
        )

        detected_encoding = None
        if charset_match:
            detected_encoding = charset_match.group(1).decode('ascii', errors='ignore').lower()
            # Normaliza nomes de encoding
            if detected_encoding in ['iso-8859-1', 'latin1', 'latin-1']:
                detected_encoding = 'iso-8859-1'
            elif detected_encoding in ['windows-1252', 'cp1252']:
                detected_encoding = 'windows-1252'

        # Lista de encodings para tentar. UTF-8 vem primeiro porque é estrito: só decodifica
        # se os bytes forem UTF-8 válidos. O coletor salva em UTF-8, mas a página do Lattes
        # declara ISO-8859-1 no <meta>; confiar no <meta> gerava mojibake em todo arquivo.
        # Latin-1 aceita qualquer byte, então precisa ficar por último.
        encodings_to_try = ['utf-8']
        if detected_encoding:
            encodings_to_try.append(detected_encoding)
        encodings_to_try.extend(['windows-1252', 'iso-8859-1'])

        # Remove duplicatas mantendo ordem
        seen = set()
        encodings_to_try = [x for x in encodings_to_try if not (x in seen or seen.add(x))]

        for encoding in encodings_to_try:
            try:
                content = raw_content.decode(encoding)
                break
            except (UnicodeDecodeError, LookupError):
                continue

        # Se nenhum encoding funcionou, força UTF-8 com substituição
        if content is None:
            content = raw_content.decode('utf-8', errors='replace')

    except Exception as e:
        return None, f"Erro ao ler arquivo {arquivo}: {e}"

    try:
        # Repara mojibake UMA VEZ no conteúdo inteiro ANTES de processar
        # Usa configurações agressivas para corrigir múltiplas camadas de corrupção
        content = ftfy.fix_text(content, **FTFY_OPCOES)

        # Parse HTML UMA VEZ e reutiliza o soup (otimização crítica)
        soup = BeautifulSoup(content, 'lxml')

        nome_pesquisador = extrair_nome_rapido(soup)
        dados = extrair_dados_lattes(soup, content, file_id)

        dados_completos = {
            'Assunto': assunto,
            'Tipo da pesquisa': tipo_pesquisa
        }
        dados_completos.update(dados)
        return dados_completos, nome_pesquisador
    except Exception as e:
        return None, f"Erro em {arquivo}: {e}"

def processar_lote_arquivos(arquivos, pasta_htmls):
    """Processa um lote de arquivos para reduzir o overhead do ProcessPoolExecutor."""
    resultados = []
    erros = []
    for arquivo in arquivos:
        res, info = processar_um_arquivo(arquivo, pasta_htmls)
        if res:
            resultados.append((res, info))
        else:
            erros.append((arquivo, info))
    return resultados, erros

def main():
    pasta_htmls = 'htmls'
    arquivos = glob.glob(os.path.join(pasta_htmls, '**', '*.html'), recursive=True)

    if not arquivos:
        print(f"Nenhum arquivo HTML encontrado em {pasta_htmls}")
        return

    contagem_pastas = Counter()
    for arquivo in arquivos:
        pasta_pai = os.path.dirname(arquivo)
        nome_pasta = os.path.basename(pasta_pai)
        if nome_pasta == pasta_htmls:
            nome_pasta = "Raiz (htmls)"
        contagem_pastas[nome_pasta] += 1

    print("\n--- Resumo de Arquivos por Pasta ---")
    for pasta, total in contagem_pastas.items():
        print(f"Pasta: {pasta} | Total: {total} arquivos")
    print("-" * 35 + "\n")

    print(f"Iniciando extração paralela de {len(arquivos)} arquivos...\n")
    lista_dados = []
    arquivos_com_erro = []
    
    # Configuração de paralelismo otimizada
    num_cpus = os.cpu_count() or 1
    # Chunk size: agrupamos arquivos para reduzir overhead de IPC (Inter-process communication)
    # Se tivermos muitos arquivos, chunks maiores ajudam. 
    # Para currículos Lattes que podem ser grandes, um tamanho de lote moderado é bom.
    chunk_size = max(1, min(len(arquivos) // (num_cpus * 4), 50))
    lotes = [arquivos[i:i + chunk_size] for i in range(0, len(arquivos), chunk_size)]

    with ProcessPoolExecutor(max_workers=num_cpus) as executor:
        futures = {executor.submit(processar_lote_arquivos, lote, pasta_htmls): lote for lote in lotes}

        with tqdm(total=len(arquivos), desc="Processando", unit="arquivo", dynamic_ncols=True) as pbar:
            for future in as_completed(futures):
                lote = futures[future]
                try:
                    lote_resultados, lote_erros = future.result()
                    
                    for res, info in lote_resultados:
                        lista_dados.append(res)
                        pbar.set_description(f"Extraído: {info[:30]:<30}")
                        pbar.update(1)
                    
                    for arq, info in lote_erros:
                        arquivos_com_erro.append(arq)
                        tqdm.write(info)
                        pbar.update(1)
                except Exception as e:
                    # O lote falhou inteiro (ex.: processo do worker morreu): todos os arquivos
                    # dele entram como erro, para não sumirem do relatório final.
                    tqdm.write(f"Erro ao processar lote de {len(lote)} arquivos: {e}")
                    arquivos_com_erro.extend(lote)
                    pbar.update(len(lote))

    # Resumo final no terminal
    total_lidos = len(arquivos)
    total_sucesso = len(lista_dados)
    total_erro = len(arquivos_com_erro)

    print("\n" + "="*50)
    print("RELATÓRIO FINAL DE EXTRAÇÃO")
    print("="*50)
    print(f"Total de arquivos lidos na pasta '{pasta_htmls}': {total_lidos}")
    print(f"Arquivos extraídos com sucesso: {total_sucesso}")
    print(f"Arquivos que deram erro no tratamento: {total_erro}")
    
    if arquivos_com_erro:
        print("\nArquivos com erro:")
        for arq in arquivos_com_erro:
            print(f"- {arq}")
    print("="*50 + "\n")

    if lista_dados:
        df = pd.DataFrame(lista_dados)
        
        # Reorganiza colunas para garantir que palavras-chave fiquem por último
        cols = list(df.columns)
        keyword_cols = [c for c in cols if c.startswith('Contagem: ') or c.startswith('Ocorrências (Colunas): ')]
        other_cols = [c for c in cols if c not in keyword_cols]
        df = df[other_cols + keyword_cols]

        # Normaliza os nomes das colunas para evitar caracteres estranhos
        df.columns = [normalizar_nome_coluna(col) for col in df.columns]
        
        # Limita o tamanho das células para o limite do Excel (32767 caracteres)
        # e remove caracteres inválidos que impedem a gravação do XML do Excel
        limite_excel = 32700
        
        # Garante que os nomes das colunas sejam únicos para evitar que df[col] retorne um DataFrame
        if not df.columns.is_unique:
            new_columns = []
            counts = {}
            for col in df.columns:
                if col in counts:
                    counts[col] += 1
                    new_columns.append(f"{col}_{counts[col]}")
                else:
                    counts[col] = 0
                    new_columns.append(col)
            df.columns = new_columns

        for col in df.columns:
            # Tratamos apenas colunas que não são numéricas puras
            if not pd.api.types.is_numeric_dtype(df[col]):
                # 1. Convertemos para string e preenchemos NaNs
                df[col] = df[col].fillna('').astype(str)

                # 2. Remove caracteres inválidos (mojibake já foi corrigido antes)
                # Agora só precisamos remover caracteres de controle inválidos no XML
                df[col] = df[col].apply(lambda x: CONTROL_CHARS_PATTERN.sub('', x.replace('\r\n', '\n').replace('\r', '\n')))

                # 3. Limpa espaços nas pontas
                df[col] = df[col].str.strip()

        # O corte no limite de caracteres por célula vale só para o Excel. O TSV sai completo.
        aviso_truncado = ' [TRUNCADO: texto completo no .txt]'
        limite_corte = limite_excel - len(aviso_truncado)
        df_excel = df.copy()
        celulas_truncadas = []
        for col in df_excel.columns:
            if pd.api.types.is_numeric_dtype(df_excel[col]):
                continue
            longas = df_excel[col].str.len() > limite_excel
            if longas.any():
                celulas_truncadas.append((col, int(longas.sum())))
                df_excel.loc[longas, col] = df_excel.loc[longas, col].str[:limite_corte] + aviso_truncado

        # Gera o nome do arquivo com data, hora e número de arquivos
        data_hora = datetime.now().strftime('%d-%m-%Y %H-%M-%S')
        num_arquivos = len(lista_dados)
        output_base = f'compilação extração - {num_arquivos} - {data_hora}'
        
        # 1. Salva como XLSX (Excel)
        output_xlsx = f'{output_base}.xlsx'
        try:
            # Tenta usar xlsxwriter se disponível, senão usa openpyxl
            try:
                import xlsxwriter
                df_excel.to_excel(output_xlsx, index=False, engine='xlsxwriter')
                print(f"\nSucesso! Arquivo Excel gerado (xlsxwriter): {output_xlsx}")
            except (ImportError, Exception):
                df_excel.to_excel(output_xlsx, index=False, engine='openpyxl')
                print(f"\nSucesso! Arquivo Excel gerado (openpyxl): {output_xlsx}")
            if celulas_truncadas:
                total_cortes = sum(n for _, n in celulas_truncadas)
                print(f"[AVISO] {total_cortes} células passaram de {limite_excel} caracteres e foram cortadas no Excel "
                      f"(marcadas com '{aviso_truncado.strip()}'). O .txt tem o texto completo.")
                for col, n in sorted(celulas_truncadas, key=lambda x: -x[1])[:10]:
                    print(f"  - {col}: {n} células")
        except Exception as e:
            print(f"\nErro ao salvar Excel: {e}")

        # 2. Salva como TXT (Tab-separated - TSV) - Excelente para Power BI
        output_txt = f'{output_base}.txt'
        try:
            df.to_csv(output_txt, index=False, sep='\t', encoding='utf-8-sig')
            print(f"Sucesso! Arquivo TXT (TSV) gerado: {output_txt}")
        except Exception as e:
            print(f"Erro ao salvar TXT: {e}")
        
        print(f"\nTotal de perfis extraídos: {len(lista_dados)}")
    else:
        print("Nenhum dado extraído.")

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    main()
